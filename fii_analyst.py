import concurrent.futures
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import pandas as pd
import yfinance as yf

from models import StockTechnical
from data_fetcher import normalize_b3_ticker, calculate_rsi

# Base de metadados dos principais FIIs do mercado brasileiro (IFIX)
FII_METADATA = {
    "HGLG11": {"nome": "CSHG Logística", "segmento": "Tijolo - Galpões Logísticos", "tipo": "Tijolo"},
    "BTLG11": {"nome": "BTG Pactual Logística", "segmento": "Tijolo - Galpões Logísticos", "tipo": "Tijolo"},
    "XPLG11": {"nome": "XP Logística", "segmento": "Tijolo - Galpões Logísticos", "tipo": "Tijolo"},
    "VILG11": {"nome": "Vinci Logística", "segmento": "Tijolo - Galpões Logísticos", "tipo": "Tijolo"},
    "KNIP11": {"nome": "Kinea Rendimentos Imobiliários", "segmento": "Papel - CRIs (IPCA+)", "tipo": "Papel"},
    "KNCR11": {"nome": "Kinea Rendimentos", "segmento": "Papel - CRIs (CDI+)", "tipo": "Papel"},
    "MXRF11": {"nome": "Maxi Renda FII", "segmento": "Papel - CRIs / Híbrido", "tipo": "Papel"},
    "RBRR11": {"nome": "RBR Rendimento High Grade", "segmento": "Papel - CRIs High Grade", "tipo": "Papel"},
    "CPTS11": {"nome": "Capitânia Securities II", "segmento": "Papel - CRIs", "tipo": "Papel"},
    "VGIR11": {"nome": "Valora RE III", "segmento": "Papel - CRIs (CDI+)", "tipo": "Papel"},
    "XPML11": {"nome": "XP Malls FII", "segmento": "Tijolo - Shoppings", "tipo": "Tijolo"},
    "VISC11": {"nome": "Vinci Shopping Centers", "segmento": "Tijolo - Shoppings", "tipo": "Tijolo"},
    "HSML11": {"nome": "HSI Malls FII", "segmento": "Tijolo - Shoppings", "tipo": "Tijolo"},
    "HGRU11": {"nome": "CSHG Renda Urbana", "segmento": "Tijolo - Varejo / Educacional", "tipo": "Tijolo"},
    "TRXF11": {"nome": "TRX Real Estate", "segmento": "Tijolo - Big Box / Varejo", "tipo": "Tijolo"},
    "ALZR11": {"nome": "Alianza Trust Renda Imobiliária", "segmento": "Híbrido - Contratos Atípicos", "tipo": "Híbrido"},
    "TGAR11": {"nome": "TG Ativo Real", "segmento": "Desenvolvimento Imobiliário", "tipo": "Híbrido"},
    "JSRE11": {"nome": "JS Real Estate", "segmento": "Tijolo - Lajes Corporativas", "tipo": "Tijolo"}
}

@dataclass
class FIIData:
    ticker: str
    nome: str
    segmento: str
    tipo_fii: str
    preco_atual: float
    pvp: Optional[float]
    dividend_yield_anual: float
    rendimento_mensal_estimado: float
    rsi_14: Optional[float]
    volume_diario: Optional[float]
    score_fii: int
    veredito: str
    tese: str
    catalisadores: List[str]
    riscos: List[str]

class FIIAnalyst:
    """Motor especializado na análise de Fundos de Investimento Imobiliário (FIIs) na B3."""

    def fetch_fii_data(self, ticker: str) -> FIIData:
        clean_ticker = ticker.upper().strip().replace(".SA", "")
        symbol = f"{clean_ticker}.SA"
        meta = FII_METADATA.get(clean_ticker, {
            "nome": f"{clean_ticker} Fundo Imobiliário",
            "segmento": "Fundo Imobiliário",
            "tipo": "Geral"
        })

        ticker_obj = yf.Ticker(symbol)
        info = ticker_obj.info or {}
        hist = ticker_obj.history(period="6mo")

        preco = info.get("currentPrice") or info.get("regularMarketPrice")
        if not preco and not hist.empty:
            preco = float(hist["Close"].iloc[-1])
        preco = round(float(preco or 0.0), 2)

        # P/VP (preço sobre valor patrimonial da cota)
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

        # Indicadores Técnicos
        rsi = None
        avg_vol = None
        if not hist.empty:
            rsi = calculate_rsi(hist["Close"])
            if "Volume" in hist.columns:
                avg_vol = float((hist["Volume"] * hist["Close"]).tail(30).mean())

        # Cálculo do Score do FII (0 a 100)
        score, veredito, tese, catalisadores, riscos = self._evaluate_fii(
            tipo=meta["tipo"],
            pvp=pvp,
            dy_anual=dy_anual,
            rsi=rsi,
            preco=preco
        )

        return FIIData(
            ticker=clean_ticker,
            nome=meta["nome"],
            segmento=meta["segmento"],
            tipo_fii=meta["tipo"],
            preco_atual=preco,
            pvp=pvp,
            dividend_yield_anual=dy_anual,
            rendimento_mensal_estimado=rend_mensal,
            rsi_14=rsi,
            volume_diario=round(avg_vol, 2) if avg_vol else None,
            score_fii=score,
            veredito=veredito,
            tese=tese,
            catalisadores=catalisadores,
            riscos=riscos
        )

    def _evaluate_fii(self, tipo: str, pvp: Optional[float], dy_anual: float, rsi: Optional[float], preco: float):
        score = 0
        catalisadores = []
        riscos = []

        # 1. Avaliação de Valuation (P/VP) - Max 40 pts
        if pvp is not None:
            if tipo == "Papel":
                # FIIs de Papel devem negociar próximos de 1.00 (evitar ágio acima de 1.05)
                if 0.95 <= pvp <= 1.02:
                    score += 40
                    catalisadores.append(f"Preço Justo em Papel: P/VP equilibrado ({pvp:.2f}x), sem pagar ágio patrimonial.")
                elif 0.85 <= pvp < 0.95:
                    score += 35
                    catalisadores.append(f"Desconto em Papel: Cota com deságio patrimonial (P/VP {pvp:.2f}x).")
                elif pvp > 1.05:
                    score += 15
                    riscos.append(f"Ágio Patrimonial: P/VP em {pvp:.2f}x indica compra de dinheiro pagando mais que R$ 1,00.")
                else:
                    score += 20
                    riscos.append(f"Desconto Severo (P/VP {pvp:.2f}x): Pode indicar risco de crédito ou inadimplência de devedores dos CRIs.")
            else:
                # FIIs de Tijolo: Desconto patrimonial pode significar oportunidade de ganho de capital
                if 0.80 <= pvp <= 0.95:
                    score += 40
                    catalisadores.append(f"Oportunidade de Ganho de Capital: Imóveis avaliados com desconto (P/VP {pvp:.2f}x).")
                elif 0.95 < pvp <= 1.02:
                    score += 30
                    catalisadores.append(f"Preço em linha com o custo de reposição dos imóveis (P/VP {pvp:.2f}x).")
                elif pvp < 0.80:
                    score += 25
                    riscos.append(f"Desconto extremo (P/VP {pvp:.2f}x): Verificar risco de vacância estrutural ou localização desfavorável.")
                else:
                    score += 15
                    riscos.append(f"Cota esticada: Imóveis negociando acima do valor contábil (P/VP {pvp:.2f}x).")
        else:
            score += 20

        # 2. Avaliação de Dividend Yield - Max 40 pts
        if dy_anual >= 12.0:
            score += 40
            catalisadores.append(f"Geração de renda excelente: Dividend Yield anual de {dy_anual:.1f}% (~{dy_anual/12:.2f}% ao mês, isento de IR).")
        elif dy_anual >= 9.5:
            score += 30
            catalisadores.append(f"Fluxo consistente de proventos (DY de {dy_anual:.1f}% a.a., superando a inflação com folga).")
        elif dy_anual >= 7.5:
            score += 20
            catalisadores.append(f"Rendimento estável e defensivo ({dy_anual:.1f}% a.a.).")
        else:
            score += 10
            riscos.append(f"Dividend Yield de {dy_anual:.1f}% a.a. pode ficar pouco competitivo frente à Selic atual.")

        # 3. Momento Técnico e Liquidez - Max 20 pts
        if rsi and rsi <= 35:
            score += 20
            catalisadores.append(f"Momento técnico favorável: Cota em sobrevenda (IFR 14 = {rsi:.1f}), com espaço para recuperação.")
        elif rsi and rsi <= 55:
            score += 15
        else:
            score += 10

        riscos.append("Sensibilidade aos juros: Taxa Selic alta eleva o custo de oportunidade e pressiona as cotas de FIIs na B3.")

        if tipo == "Tijolo":
            riscos.append("Risco imobiliário: Vacância física e revisão de contratos de aluguel.")
        elif tipo == "Papel":
            riscos.append("Risco de crédito privado: Exposição à capacidade de pagamento dos emissores de Certificados de Recebíveis Imobiliários (CRIs).")

        # Veredito
        if score >= 75:
            veredito = "COMPRA"
            tese = "Fundo imobiliário com excelente assimetria entre proventos mensais e valor patrimonial, remunerando o investidor acima da média do mercado com risco controlado."
        elif score >= 55:
            veredito = "MANTER"
            tese = "FII com precificação condizente com a qualidade dos ativos, ideal para composição de renda mensal passiva sem pressa de valorização rápida."
        else:
            veredito = "VENDA / EVITAR"
            tese = "Preço esticado frente ao valor patrimonial ou rendimento comprimido diante do risco incorrido."

        return score, veredito, tese, catalisadores, riscos

    def scan_fiis(self, top_n: int = 5) -> List[FIIData]:
        """Varredura dos principais FIIs listados para identificar as melhores oportunidades."""
        tickers = list(FII_METADATA.keys())
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_fii = {executor.submit(self.fetch_fii_data, t): t for t in tickers}
            for future in concurrent.futures.as_completed(future_to_fii):
                try:
                    data = future.result()
                    if data.preco_atual > 0:
                        results.append(data)
                except Exception:
                    pass

        results.sort(key=lambda x: x.score_fii, reverse=True)
        return results[:top_n]
