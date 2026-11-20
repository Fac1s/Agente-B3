import concurrent.futures
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import yfinance as yf

from data_fetcher import calculate_rsi

# Base enriquecida com mais de 25 FIIs mais negociados do IFIX
FII_METADATA = {
    # Galpões Logísticos (Tijolo)
    "HGLG11": {"nome": "CSHG Logística", "segmento": "Tijolo - Logística", "tipo": "Tijolo", "perfil": "Triple A / Sudeste"},
    "BTLG11": {"nome": "BTG Pactual Logística", "segmento": "Tijolo - Logística", "tipo": "Tijolo", "perfil": "Galpões / Contratos Atípicos"},
    "XPLG11": {"nome": "XP Logística", "segmento": "Tijolo - Logística", "tipo": "Tijolo", "perfil": "Galpões Logísticos"},
    "VILG11": {"nome": "Vinci Logística", "segmento": "Tijolo - Logística", "tipo": "Tijolo", "perfil": "Diversificado Regional"},
    "BRCO11": {"nome": "Bresco Logística", "segmento": "Tijolo - Logística", "tipo": "Tijolo", "perfil": "Triple A / Raio 30km SP"},
    
    # Shoppings (Tijolo)
    "XPML11": {"nome": "XP Malls", "segmento": "Tijolo - Shoppings", "tipo": "Tijolo", "perfil": "Shoppings Dominantes"},
    "VISC11": {"nome": "Vinci Shopping Centers", "segmento": "Tijolo - Shoppings", "tipo": "Tijolo", "perfil": "Multi-ativos / Brasil"},
    "HSML11": {"nome": "HSI Malls", "segmento": "Tijolo - Shoppings", "tipo": "Tijolo", "perfil": "Shoppings Consolidados"},

    # Renda Urbana / Híbridos (Tijolo)
    "HGRU11": {"nome": "CSHG Renda Urbana", "segmento": "Tijolo - Renda Urbana", "tipo": "Tijolo", "perfil": "Varejo Alimentício e Educacional"},
    "TRXF11": {"nome": "TRX Real Estate", "segmento": "Tijolo - Big Box", "tipo": "Tijolo", "perfil": "Atacarejo e Lojas Âncora"},
    "ALZR11": {"nome": "Alianza Trust Renda", "segmento": "Tijolo - Contratos Atípicos", "tipo": "Tijolo", "perfil": "Longo Prazo / Atípicos"},

    # Lajes Corporativas (Tijolo)
    "JSRE11": {"nome": "JS Real Estate", "segmento": "Tijolo - Lajes Corporativas", "tipo": "Tijolo", "perfil": "Escritórios SP"},
    "PVBI11": {"nome": "VBI Prime Properties", "segmento": "Tijolo - Lajes Corporativas", "tipo": "Tijolo", "perfil": "Faria Lima / Itaim / Vila Olímpia"},

    # Papel / CRIs - High Grade (Risco Baixo a Médio)
    "KNIP11": {"nome": "Kinea Rendimentos Imob.", "segmento": "Papel - CRIs (IPCA+)", "tipo": "Papel", "perfil": "High Grade / Indexado a IPCA"},
    "KNCR11": {"nome": "Kinea Rendimentos", "segmento": "Papel - CRIs (CDI+)", "tipo": "Papel", "perfil": "High Grade / Pós-Fixado CDI"},
    "RBRR11": {"nome": "RBR Rendimento High Grade", "segmento": "Papel - CRIs (IPCA/CDI)", "tipo": "Papel", "perfil": "Garantias Fortes / Devedores Sólidos"},
    "MCCI11": {"nome": "Mauá Capital Recebíveis", "segmento": "Papel - CRIs", "tipo": "Papel", "perfil": "High Grade / Diversificado"},

    # Papel / CRIs - Híbridos e Médio Risco
    "MXRF11": {"nome": "Maxi Renda FII", "segmento": "Papel - CRIs / Híbrido", "tipo": "Papel", "perfil": "CRIs + Permutas Financeiras"},
    "CPTS11": {"nome": "Capitânia Securities II", "segmento": "Papel - CRIs", "tipo": "Papel", "perfil": "Liquidez / Giro de Carteira"},
    "VGIR11": {"nome": "Valora RE III", "segmento": "Papel - CRIs (CDI+)", "tipo": "Papel", "perfil": "Pós-fixado / Spread CDI"},
    "SNCI11": {"nome": "Suno Recebíveis Imob.", "segmento": "Papel - CRIs", "tipo": "Papel", "perfil": "Diversificado / High Grade"},

    # Desenvolvimento e FoFs
    "TGAR11": {"nome": "TG Ativo Real", "segmento": "Desenvolvimento Imobiliário", "tipo": "Híbrido", "perfil": "Loteamentos e Equity"},
    "KFOF11": {"nome": "Kinea FOF", "segmento": "Fundo de Fundos", "tipo": "Híbrido", "perfil": "Cotas de outros FIIs com duplo desconto"}
}

BENCHMARK_NTNB_TAXA = 6.70  # Taxa de referência do Tesouro IPCA+ longo (%)

@dataclass
class FIIData:
    ticker: str
    nome: str
    segmento: str
    tipo_fii: str
    perfil: str
    preco_atual: float
    pvp: Optional[float]
    dividend_yield_anual: float
    rendimento_mensal_estimado: float
    rendimento_bruto_equivalente: float
    spread_vs_ntnb: float
    diagnostico_desconto: str
    is_value_trap_risk: bool
    rsi_14: Optional[float]
    volume_diario: Optional[float]
    score_fii: int
    veredito: str
    tese: str
    catalisadores: List[str]
    riscos: List[str]

class FIIAnalyst:
    """Motor especializado com análise avançada de FIIs: Spreads de Yield, Diagnóstico de Desconto e Filtro Anti-Ciladas."""

    def fetch_fii_data(self, ticker: str) -> FIIData:
        clean_ticker = ticker.upper().strip().replace(".SA", "")
        symbol = f"{clean_ticker}.SA"
        meta = FII_METADATA.get(clean_ticker, {
            "nome": f"{clean_ticker} FII",
            "segmento": "Fundo Imobiliário",
            "tipo": "Geral",
            "perfil": "Não classificado"
        })

        ticker_obj = yf.Ticker(symbol)
        info = ticker_obj.info or {}
        hist = ticker_obj.history(period="6mo")

        preco = info.get("currentPrice") or info.get("regularMarketPrice")
        if not preco and not hist.empty:
            preco = float(hist["Close"].iloc[-1])
        preco = round(float(preco or 0.0), 2)

        # P/VP
        pvp_raw = info.get("priceToBook")
        pvp = round(float(pvp_raw), 2) if pvp_raw else None

        # Dividend Yield
        dy_raw = info.get("dividendYield") or 0.0
        if dy_raw > 1.0:
            dy_anual = round(float(dy_raw), 2)
        elif dy_raw > 0:
            dy_anual = round(float(dy_raw) * 100, 2)
        else:
            dy_anual = 0.0

        rend_mensal = round((dy_anual / 12), 2)
        
        # Rendimento bruto equivalente (FII é isento de IR, comparando com renda fixa tributada a 15%):
        rend_bruto_equiv = round(dy_anual / (1 - 0.15), 2) if dy_anual > 0 else 0.0

        # Spread sobre o Tesouro IPCA+
        spread = round(dy_anual - BENCHMARK_NTNB_TAXA, 2)

        # IFR e Volume
        rsi = None
        avg_vol = None
        if not hist.empty:
            rsi = calculate_rsi(hist["Close"])
            if "Volume" in hist.columns:
                avg_vol = float((hist["Volume"] * hist["Close"]).tail(30).mean())

        # Diagnóstico Profundo do Desconto e Avaliação de Risco
        score, veredito, diagnostico, is_trap, tese, catalisadores, riscos = self._evaluate_advanced_fii(
            tipo=meta["tipo"],
            segmento=meta["segmento"],
            pvp=pvp,
            dy_anual=dy_anual,
            spread=spread,
            rsi=rsi
        )

        return FIIData(
            ticker=clean_ticker,
            nome=meta["nome"],
            segmento=meta["segmento"],
            tipo_fii=meta["tipo"],
            perfil=meta["perfil"],
            preco_atual=preco,
            pvp=pvp,
            dividend_yield_anual=dy_anual,
            rendimento_mensal_estimado=rend_mensal,
            rendimento_bruto_equivalente=rend_bruto_equiv,
            spread_vs_ntnb=spread,
            diagnostico_desconto=diagnostico,
            is_value_trap_risk=is_trap,
            rsi_14=rsi,
            volume_diario=round(avg_vol, 2) if avg_vol else None,
            score_fii=score,
            veredito=veredito,
            tese=tese,
            catalisadores=catalisadores,
            riscos=riscos
        )

    def _evaluate_advanced_fii(self, tipo: str, segmento: str, pvp: Optional[float], dy_anual: float, spread: float, rsi: Optional[float]):
        score = 0
        catalisadores = []
        riscos = []
        is_trap = False
        diagnostico = "Preço em linha de mercado"

        # 1. Avaliação de Valuation & Diagnóstico de Desconto (35 pontos)
        if pvp is not None:
            if tipo == "Tijolo":
                if 0.75 <= pvp <= 0.92:
                    score += 35
                    diagnostico = "💎 Barganha Real (Desconto Patrimonial em Imóveis Físicos)"
                    catalisadores.append(f"Custo de reposição atrativo: Cota negociando a {pvp:.2f}x do valor contábil dos imóveis.")
                elif 0.92 < pvp <= 1.02:
                    score += 25
                    diagnostico = "Preço Justo (Alinhado ao patrimônio dos imóveis)"
                    catalisadores.append(f"Precificação equilibrada de patrimônio (P/VP {pvp:.2f}x).")
                elif pvp < 0.75:
                    score += 15
                    is_trap = True
                    diagnostico = "⚠️ Alerta de Cilada / Armadilha (Risco de Vacância Crônica ou Lajes Antigas)"
                    riscos.append(f"Desconto extremo (P/VP {pvp:.2f}x): Pode indicar perda estrutural de inquilinos ou imóveis defasados.")
                else:
                    score += 10
                    diagnostico = "Cota Esticada (Negociando acima do valor contábil)"
                    riscos.append(f"Ágio Patrimonial: P/VP em {pvp:.2f}x reduz a margem de segurança.")
            elif tipo == "Papel":
                if 0.92 <= pvp <= 1.02:
                    score += 35
                    diagnostico = "💎 Oportunidade em Papel (Sem ágio e com spread de crédito)"
                    catalisadores.append(f"Preço Justo em CRIs: P/VP de {pvp:.2f}x sem pagar ágio sobre dinheiro.")
                elif 0.85 <= pvp < 0.92:
                    score += 28
                    diagnostico = "Deságio em Crédito (Marcação a mercado de CRIs)"
                    catalisadores.append(f"Cota com deságio frente aos recebíveis (P/VP {pvp:.2f}x).")
                elif pvp < 0.85:
                    score += 10
                    is_trap = True
                    diagnostico = "🚨 Risco de Inadimplência / Calote em CRIs (High Yield Estressado)"
                    riscos.append(f"P/VP muito deprimido ({pvp:.2f}x): Mercado precificando perda definitiva de crédito ou calote de devedores.")
                else:
                    score += 10
                    diagnostico = "Ágio em Papel (Evite pagar mais que R$ 1,00 por dinheiro)"
                    riscos.append(f"P/VP de {pvp:.2f}x em fundo de papel é desfavorável.")
        else:
            score += 20

        # 2. Avaliação de Proventos & Spread vs NTN-B (35 pontos)
        if spread >= 3.0:
            score += 35
            catalisadores.append(f"Spread Soberano Excelente: DY de {dy_anual:.1f}% supera a taxa do Tesouro IPCA+ em +{spread:.1f}% ao ano.")
        elif spread >= 1.5:
            score += 25
            catalisadores.append(f"Prêmio Atrativo: DY de {dy_anual:.1f}% a.a. oferece prêmio de +{spread:.1f}% sobre o Tesouro.")
        elif spread >= 0:
            score += 15
            catalisadores.append(f"Yield alinhado à taxa soberana real ({dy_anual:.1f}% a.a.).")
        else:
            score += 5
            riscos.append(f"Spread Negativo ({spread:.1f}%): O fundo remunera menos que a taxa livre de risco do Tesouro Nacional.")

        # 3. Momento Técnico e Sobrevenda (15 pontos)
        if rsi and rsi <= 35:
            score += 15
            catalisadores.append(f"Sobrevenda Técnica: IFR 14 em {rsi:.1f} indica venda por pânico e ponto de reversão favorável.")
        elif rsi and rsi <= 55:
            score += 10
        else:
            score += 5

        # 4. Solidez e Perfil (15 pontos)
        if "Logística" in segmento or "Shoppings" in segmento:
            score += 15
            catalisadores.append("Ativos resilientes e alta demanda de locação.")
        else:
            score += 10

        # Penalização se for armadilha de valor
        if is_trap:
            score = round(score * 0.60)

        # Veredito
        if score >= 75 and not is_trap:
            veredito = "COMPRA"
            tese = (
                f"Fundo imobiliário em momento de excelente assimetria ({diagnostico}). "
                f"O Dividend Yield isento de {dy_anual:.1f}% a.a. oferece margem de segurança de +{spread:.1f}% "
                f"acima do Tesouro IPCA+, permitindo capturar tanto renda mensal como potencial reprecificação de cota."
            )
        elif score >= 50:
            veredito = "MANTER"
            tese = f"Fundo com precificação estável ({diagnostico}). Adequado para carrego de renda passiva mensal."
        else:
            veredito = "CUIDADO / EVITAR"
            tese = f"Fundo com alerta de risco ({diagnostico}). O desconto atual pode ser reflexo de deterioração de portfólio."

        return score, veredito, diagnostico, is_trap, tese, catalisadores, riscos

    def scan_fiis(self, top_n: int = 10, apenas_barganhas: bool = False) -> List[FIIData]:
        """Varredura concorrente de múltiplos FIIs com ordenação inteligente."""
        tickers = list(FII_METADATA.keys())
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_fii = {executor.submit(self.fetch_fii_data, t): t for t in tickers}
            for future in concurrent.futures.as_completed(future_to_fii):
                try:
                    data = future.result()
                    if data.preco_atual > 0:
                        if apenas_barganhas and data.is_value_trap_risk:
                            continue
                        results.append(data)
                except Exception:
                    pass

        results.sort(key=lambda x: x.score_fii, reverse=True)
        return results[:top_n]
