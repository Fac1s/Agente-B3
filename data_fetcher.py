import datetime
from typing import Optional, Tuple
import pandas as pd
import yfinance as yf
from models import StockFundamentals, StockTechnical, StockData

def normalize_b3_ticker(ticker: str) -> str:
    """Garante que o ticker termine com .SA para a B3 no Yahoo Finance."""
    ticker_clean = ticker.strip().upper()
    if not ticker_clean.endswith(".SA"):
        return f"{ticker_clean}.SA"
    return ticker_clean

def calculate_rsi(prices: pd.Series, period: int = 14) -> Optional[float]:
    """Calcula o Índice de Força Relativa (IFR / RSI)."""
    if len(prices) < period + 1:
        return None
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    last_rsi = rsi.iloc[-1]
    if pd.isna(last_rsi):
        return None
    return round(float(last_rsi), 2)

def fetch_b3_stock(ticker: str) -> StockData:
    """Coleta dados fundamentalistas e técnicos de uma ação da B3."""
    clean_symbol = normalize_b3_ticker(ticker)
    ticker_obj = yf.Ticker(clean_symbol)
    
    # 1. Informações cadastrais e múltiplos
    info = ticker_obj.info or {}
    
    # 2. Histórico para análise técnica (6 meses)
    hist = ticker_obj.history(period="6mo")
    
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not current_price and not hist.empty:
        current_price = float(hist["Close"].iloc[-1])
    current_price = round(float(current_price or 0.0), 2)
    
    # Múltiplos com tratamento de None e conversão segura
    pe = info.get("trailingPE") or info.get("forwardPE")
    pb = info.get("priceToBook")
    ev_ebitda = info.get("enterpriseToEbitda")
    
    dy_raw = info.get("dividendYield") or 0.0
    # No Yahoo Finance, algumas ações trazem 0.0809 (decimal) e outras 8.09 (%):
    if dy_raw > 1.0:
        dy = round(float(dy_raw), 2)
    elif dy_raw > 0:
        dy = round(float(dy_raw) * 100, 2)
    else:
        dy = 0.0
    
    payout_raw = info.get("payoutRatio") or 0.0
    payout = round(payout_raw * 100, 2) if payout_raw else None
    
    roe_raw = info.get("returnOnEquity") or 0.0
    roe = round(roe_raw * 100, 2) if roe_raw else None
    
    net_margin_raw = info.get("profitMargins") or 0.0
    net_margin = round(net_margin_raw * 100, 2) if net_margin_raw else None
    
    ebitda_margin_raw = info.get("ebitdaMargins") or 0.0
    ebitda_margin = round(ebitda_margin_raw * 100, 2) if ebitda_margin_raw else None
    
    # Dívida / EBITDA aproximada
    debt_ebitda = None
    total_debt = info.get("totalDebt")
    ebitda = info.get("ebitda")
    total_cash = info.get("totalCash")
    if total_debt is not None and ebitda is not None and ebitda > 0:
        net_debt = total_debt - (total_cash or 0)
        debt_ebitda = round(net_debt / ebitda, 2)
        
    fundamentals = StockFundamentals(
        ticker=ticker.upper().replace(".SA", ""),
        company_name=info.get("longName") or info.get("shortName") or ticker.upper(),
        sector=info.get("sector") or "Não Informado",
        industry=info.get("industry") or "Não Informado",
        current_price=current_price,
        market_cap=info.get("marketCap"),
        pe_ratio=round(pe, 2) if pe else None,
        pb_ratio=round(pb, 2) if pb else None,
        ev_ebitda=round(ev_ebitda, 2) if ev_ebitda else None,
        dividend_yield=dy,
        payout_ratio=payout,
        roe=roe,
        net_margin=net_margin,
        ebitda_margin=ebitda_margin,
        debt_to_ebitda=debt_ebitda,
        free_cashflow=info.get("freeCashflow")
    )
    
    # 3. Análise Técnica e Médias Móveis
    high_52w = info.get("fiftyTwoWeekHigh")
    low_52w = info.get("fiftyTwoWeekLow")
    sma_50 = None
    sma_200 = None
    rsi_14 = None
    avg_vol = None
    
    if not hist.empty:
        closes = hist["Close"]
        if len(closes) >= 50:
            sma_50 = round(float(closes.rolling(50).mean().iloc[-1]), 2)
        if len(closes) >= 200:
            sma_200 = round(float(closes.rolling(200).mean().iloc[-1]), 2)
        rsi_14 = calculate_rsi(closes)
        
        # Volume financeiro médio diário aproximado (Preço * Volume em R$)
        if "Volume" in hist.columns:
            recent_vol = hist["Volume"].tail(30)
            recent_close = hist["Close"].tail(30)
            avg_vol = round(float((recent_vol * recent_close).mean()), 2)
            
    technical = StockTechnical(
        current_price=current_price,
        high_52w=round(high_52w, 2) if high_52w else None,
        low_52w=round(low_52w, 2) if low_52w else None,
        sma_50=sma_50,
        sma_200=sma_200,
        rsi_14=rsi_14,
        avg_volume_30d=avg_vol
    )
    
    return StockData(
        ticker=fundamentals.ticker,
        fundamentals=fundamentals,
        technical=technical,
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

if __name__ == "__main__":
    import sys
    test_ticker = sys.argv[1] if len(sys.argv) > 1 else "PETR4"
    print(f"Buscando dados para {test_ticker}...")
    try:
        data = fetch_b3_stock(test_ticker)
        print("Sucesso:")
        print(data.model_dump_json(indent=2))
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
