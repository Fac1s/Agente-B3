import concurrent.futures
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from models import StockData, AnalysisReport
from data_fetcher import fetch_b3_stock
from analyst import B3StockAnalyst, strip_accents

# ==============================================================================
# UNIVERSOS DE AÇÕES DA B3
# ==============================================================================

# 1. Composição Completa do IBOVESPA (~86 ativos mais representativos)
IBOVESPA_UNIVERSE = [
    "ABEV3", "ALOS3", "ARZZ3", "ASAI3", "AZUL4", "B3SA3", "BBAS3", "BBDC3", "BBDC4",
    "BBSE3", "BEEF3", "BHIA3", "BRAP4", "BRFS3", "BRKM5", "CCRO3", "CIEL3", "CMIG4",
    "CMIN3", "COGN3", "CPFE3", "CPLE6", "CRFB3", "CSAN3", "CSNA3", "CVCB3", "CYRE3",
    "DXCO3", "EGIE3", "ELET3", "ELET6", "EMBR3", "ENEV3", "ENGI11", "EQTL3", "EZTC3",
    "FLRY3", "GGBR4", "GOAU4", "GOLL4", "HAPV3", "HYPE3", "IGTI11", "IRBR3", "ITSA4",
    "ITUB4", "JBSS3", "KLBN11", "LREN3", "LWSA3", "MGLU3", "MRFG3", "MRVE3", "MULT3",
    "NTCO3", "PCAR3", "PETR3", "PETR4", "PETZ3", "PRIO3", "RADL3", "RAIZ4", "RDOR3",
    "RECV3", "RENT3", "RRRP3", "SANB11", "SBSP3", "SLCE3", "SMTO3", "SOMA3", "SUZB3",
    "TAEE11", "TIMS3", "TOTS3", "UGPA3", "USIM5", "VALE3", "VBBR3", "VIIA3", "VIVT3",
    "VIVA3", "WEGE3", "YDUQ3"
]

# 2. Universo de Small Caps (Empresas menores com alto potencial de multiplicação/assimetria)
SMALLCAPS_UNIVERSE = [
    "AURE3", "BLAT3", "CAML3", "CBAV3", "CEAB3", "CURY3", "DIRR3", "FESA4", "FRAS3",
    "GFSA3", "GRND3", "INTB3", "JALL3", "KEPL3", "LEVE3", "LOGG3", "MDNE3", "MOVI3",
    "MYPK3", "ORVR3", "PLPL3", "POMO4", "PORT3", "POSI3", "RANI3", "RAPT4", "SEQL3",
    "SHUL4", "SIMH3", "TEND3", "TGMA3", "TRIS3", "TTEN3", "VAMO3", "VLID3", "VULC3",
    "WIZC3"
]

# 3. Universo de Dividendos (Empresas geradoras de caixa / IDIV)
DIVIDENDOS_UNIVERSE = [
    "BBAS3", "BBSE3", "CXSE3", "CPFE3", "CPLE6", "EGIE3", "CMIG4", "TAEE11", "TRPL4",
    "SANB11", "ITUB4", "BBDC4", "PETR4", "VALE3", "VIVT3", "TIMS3", "CSNA3", "GGBR4",
    "GOAU4", "VBBR3", "PSSA3", "ALUP11", "ENAT3"
]

# Universo padrão equilibrado
DEFAULT_B3_UNIVERSE = IBOVESPA_UNIVERSE

def get_universe_by_name(name: str) -> List[str]:
    """Retorna o universo desejado de acordo com o filtro do usuário."""
    name_clean = name.lower().strip()
    if name_clean in ["ibov", "ibovespa"]:
        return list(dict.fromkeys(IBOVESPA_UNIVERSE))
    elif name_clean in ["small", "smallcaps", "smll"]:
        return list(dict.fromkeys(SMALLCAPS_UNIVERSE))
    elif name_clean in ["div", "dividendos", "idiv"]:
        return list(dict.fromkeys(DIVIDENDOS_UNIVERSE))
    elif name_clean in ["all", "completo", "todos"]:
        # Combinação de todos os universos sem duplicatas (110+ ativos)
        return list(dict.fromkeys(IBOVESPA_UNIVERSE + SMALLCAPS_UNIVERSE + DIVIDENDOS_UNIVERSE))
    else:
        return list(dict.fromkeys(IBOVESPA_UNIVERSE))

class OpportunityScore(BaseModel):
    ticker: str
    company_name: str
    sector: str
    current_price: float
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    dividend_yield: Optional[float] = None
    roe: Optional[float] = None
    debt_to_ebitda: Optional[float] = None
    rsi_14: Optional[float] = None
    avg_daily_volume: Optional[float] = None
    
    # Pontuações do Screener
    deep_value_score: int = Field(..., ge=0, le=100, description="Nível de desconto em múltiplos")
    quality_score: int = Field(..., ge=0, le=100, description="Qualidade operacional e retorno")
    catalyst_score: int = Field(..., ge=0, le=100, description="Gatilhos e assimetria técnica/macro")
    total_upside_score: int = Field(..., ge=0, le=100, description="Score Geral de Assimetria e Potencial de Valorização")
    
    is_value_trap_risk: bool = False
    trap_reasons: List[str] = []
    primary_thesis: str = ""

class MarketScreeningReport(BaseModel):
    timestamp: str
    universe_size: int
    analyzed_count: int
    top_opportunities: List[OpportunityScore]
    summary_markdown: str

class B3MarketScreener:
    """Motor de varredura de mercado para garimpar empresas muito descontadas com alto potencial."""

    def __init__(self, tickers: Optional[List[str]] = None, universe: str = "ibov", max_workers: int = 10):
        if tickers:
            self.tickers = tickers
        else:
            self.tickers = get_universe_by_name(universe)
        self.universe_name = universe.upper()
        self.max_workers = max_workers

    def evaluate_opportunity(self, stock: StockData) -> OpportunityScore:
        funds = stock.fundamentals
        tech = stock.technical
        
        sector_clean = strip_accents(funds.sector)
        is_financial = any(w in sector_clean for w in ["financ", "banc", "bank", "segur", "insur"])
        
        # 1. Avaliação de Deep Value (Desconto Severo) - Max 100 pts
        val_score = 0
        # P/L
        if funds.pe_ratio is not None and funds.pe_ratio > 0:
            if funds.pe_ratio <= 5.0:
                val_score += 40
            elif funds.pe_ratio <= 8.0:
                val_score += 30
            elif funds.pe_ratio <= 12.0:
                val_score += 15
        
        # P/VP (negociando abaixo do patrimônio é sinal clássico de Deep Value)
        if funds.pb_ratio is not None and funds.pb_ratio > 0:
            if funds.pb_ratio <= 0.8:
                val_score += 35
            elif funds.pb_ratio <= 1.1:
                val_score += 25
            elif funds.pb_ratio <= 1.5:
                val_score += 10
                
        # EV/EBITDA (se aplicável)
        if not is_financial and funds.ev_ebitda is not None and funds.ev_ebitda > 0:
            if funds.ev_ebitda <= 4.0:
                val_score += 25
            elif funds.ev_ebitda <= 6.5:
                val_score += 15
        elif is_financial:
            val_score += 20 # Bônus neutro para bancos onde EV/EBITDA não existe
            
        deep_val_score = min(val_score, 100)

        # 2. Qualidade Operacional (Proteção contra Armadilhas de Valor) - Max 100 pts
        qual_score = 0
        if funds.roe is not None:
            if funds.roe >= 20.0:
                qual_score += 45
            elif funds.roe >= 14.0:
                qual_score += 30
            elif funds.roe >= 8.0:
                qual_score += 15
                
        if funds.net_margin is not None:
            if funds.net_margin >= 15.0:
                qual_score += 30
            elif funds.net_margin >= 8.0:
                qual_score += 20
            elif funds.net_margin >= 3.0:
                qual_score += 10
                
        # Dívida equilibrada (essencial para que o desconto vire lucro e não falência sob Selic alta)
        if is_financial:
            qual_score += 25
        elif funds.debt_to_ebitda is not None:
            if funds.debt_to_ebitda <= 1.5:
                qual_score += 25
            elif funds.debt_to_ebitda <= 2.5:
                qual_score += 15
            elif funds.debt_to_ebitda <= 3.5:
                qual_score += 5
        else:
            qual_score += 10
            
        quality_score = min(qual_score, 100)

        # 3. Gatilhos / Catalisadores (Horizonte Favorável) - Max 100 pts
        cat_score = 0
        # Dividend Yield elevado (fornece piso de proteção e remuneração enquanto aguarda reprecificação)
        if funds.dividend_yield is not None:
            if funds.dividend_yield >= 8.0:
                cat_score += 40
            elif funds.dividend_yield >= 5.0:
                cat_score += 25
                
        # Assimetria técnica: Sobrevenda no IFR (RSI) ou espaço para alta
        if tech.rsi_14 is not None:
            if tech.rsi_14 <= 30.0:
                cat_score += 35 # Sobrevenda extrema: alta assimetria de repique
            elif tech.rsi_14 <= 45.0:
                cat_score += 25
            elif tech.rsi_14 <= 60.0:
                cat_score += 10
                
        # Distância das médias (se estiver descontada frente à MM200)
        if tech.sma_200 and funds.current_price < tech.sma_200:
            cat_score += 25
        else:
            cat_score += 10
            
        catalyst_score = min(cat_score, 100)

        # 4. Detecção de "Value Trap" (Armadilha de Valor)
        trap_reasons = []
        is_trap = False
        
        if not is_financial and funds.debt_to_ebitda and funds.debt_to_ebitda > 4.0:
            is_trap = True
            trap_reasons.append(f"Alavancagem perigosa: Dívida/EBITDA de {funds.debt_to_ebitda:.2f}x sob Selic alta.")
            
        if funds.roe and funds.roe < 0:
            is_trap = True
            trap_reasons.append("Prejuízo recorrente: ROE negativo.")
            
        if tech.avg_volume_30d and tech.avg_volume_30d < 1_000_000:
            is_trap = True
            trap_reasons.append("Iliquidez crítica: Volume diário abaixo de R$ 1M.")

        # 5. Cálculo do Total Upside Score Ponderado
        # 40% Desconto, 35% Qualidade (evita quebrar), 25% Catalisadores
        raw_total = (deep_val_score * 0.40) + (quality_score * 0.35) + (catalyst_score * 0.25)
        
        # Penaliza severamente se for identificada armadilha de valor
        if is_trap:
            raw_total = raw_total * 0.50
            
        total_score = round(raw_total)

        # Resumo da Tese de Assimetria
        thesis_parts = []
        if deep_val_score >= 60:
            thesis_parts.append("Múltiplos altamente deprimidos com ampla margem de segurança")
        if quality_score >= 60:
            thesis_parts.append("balanço resiliente e geração sólida de caixa")
        if catalyst_score >= 50:
            thesis_parts.append("gatilho técnico ou proventos que remuneram a espera")
            
        thesis = ", com ".join(thesis_parts) if thesis_parts else "Múltiplos neutros em consolidação."

        return OpportunityScore(
            ticker=funds.ticker,
            company_name=funds.company_name,
            sector=funds.sector,
            current_price=funds.current_price,
            pe_ratio=funds.pe_ratio,
            pb_ratio=funds.pb_ratio,
            ev_ebitda=funds.ev_ebitda,
            dividend_yield=funds.dividend_yield,
            roe=funds.roe,
            debt_to_ebitda=funds.debt_to_ebitda,
            rsi_14=tech.rsi_14,
            avg_daily_volume=tech.avg_volume_30d,
            deep_value_score=deep_val_score,
            quality_score=quality_score,
            catalyst_score=catalyst_score,
            total_upside_score=total_score,
            is_value_trap_risk=is_trap,
            trap_reasons=trap_reasons,
            primary_thesis=thesis
        )

    def scan_market(self, top_n: int = 5) -> MarketScreeningReport:
        """Executa a varredura paralela no mercado da B3 e elenca as melhores oportunidades de assimetria."""
        print(f"Varrendo universo de {len(self.tickers)} ações da B3...")
        collected_data: List[StockData] = []

        def _fetch(ticker: str) -> Optional[StockData]:
            try:
                return fetch_b3_stock(ticker)
            except Exception as e:
                # Log silencioso de ticker com erro temporário
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ticker = {executor.submit(_fetch, t): t for t in self.tickers}
            for future in concurrent.futures.as_completed(future_to_ticker):
                res = future.result()
                if res and res.fundamentals.current_price > 0:
                    collected_data.append(res)

        print(f"Dados coletados com sucesso para {len(collected_data)} ativos.")

        # Avalia cada ativo
        scores = [self.evaluate_opportunity(s) for s in collected_data]
        
        # Filtra e ordena: maiores scores primeiro, excluindo armadilhas de valor
        healthy_opportunities = [s for s in scores if not s.is_value_trap_risk]
        healthy_opportunities.sort(key=lambda x: x.total_upside_score, reverse=True)
        
        top_picks = healthy_opportunities[:top_n]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Elabora o resumo executivo em Markdown
        summary_md = self._build_markdown_report(top_picks, len(self.tickers), len(collected_data), now_str)

        return MarketScreeningReport(
            timestamp=now_str,
            universe_size=len(self.tickers),
            analyzed_count=len(collected_data),
            top_opportunities=top_picks,
            summary_markdown=summary_md
        )

    def _build_markdown_report(self, top_picks: List[OpportunityScore], total: int, analyzed: int, timestamp: str) -> str:
        lines = [
            "# 🎯 Varredura B3: Oportunidades de Assimetria e Deep Value",
            f"**Data da Varredura:** {timestamp}  ",
            f"**Universo Monitorado:** {analyzed} de {total} ativos líquidos da B3 analisados  ",
            "",
            "> **Critério do Agente:** Identificação de empresas com desconto severo de múltiplos (P/L e P/VP deprimidos), balanço resiliente para suportar a Selic atual e gatilhos favoráveis de reprecificação (reversão técnica ou proventos elevados), expurgando *Value Traps* (armadilhas de endividamento).",
            "",
            "## 🏆 Ranking das Melhores Oportunidades Encontradas",
            "",
            "| Ranking | Ticker | Empresa | Setor | Preço Atual | P/L | P/VP | ROE | DY | IFR 14 | Upside Score |",
            "| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        ]

        for i, opp in enumerate(top_picks, 1):
            pl_str = f"{opp.pe_ratio:.1f}" if opp.pe_ratio else "N/A"
            pvp_str = f"{opp.pb_ratio:.2f}" if opp.pb_ratio else "N/A"
            roe_str = f"{opp.roe:.1f}%" if opp.roe else "N/A"
            dy_str = f"{opp.dividend_yield:.1f}%" if opp.dividend_yield else "0.0%"
            rsi_str = f"{opp.rsi_14:.1f}" if opp.rsi_14 else "N/A"
            lines.append(
                f"| #{i} | **{opp.ticker}** | {opp.company_name[:20]} | {opp.sector[:18]} | "
                f"R$ {opp.current_price:.2f} | {pl_str} | {pvp_str} | {roe_str} | {dy_str} | {rsi_str} | **{opp.total_upside_score}/100** |"
            )

        lines.append("")
        lines.append("---")
        lines.append("## 🔍 Detalhamento das Teses de Reprecificação")
        lines.append("")

        for i, opp in enumerate(top_picks, 1):
            lines.append(f"### #{i} - {opp.ticker} ({opp.company_name})")
            lines.append(f"* **Preço Atual:** R$ {opp.current_price:.2f} | **Upside Score:** **{opp.total_upside_score} / 100**")
            lines.append(f"* **Score de Desconto (Deep Value):** {opp.deep_value_score}/100")
            lines.append(f"* **Score de Qualidade Operacional:** {opp.quality_score}/100")
            lines.append(f"* **Score de Catalisadores:** {opp.catalyst_score}/100")
            lines.append(f"* **Tese Central:** {opp.primary_thesis.capitalize()}.")
            lines.append("")

        return "\n".join(lines)
