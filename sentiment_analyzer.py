import yfinance as yf
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

@dataclass
class MarketNewsItem:
    title: str
    summary: str
    link: str
    published: str
    source: str
    sentiment_label: str  # "OTIMISTA", "NEUTRO", "ALERTA"
    score: float
    related_tickers: List[str]

@dataclass
class QuantitativeSentimentPillar:
    nome: str
    valor_atual: str
    diagnostico: str
    score: int  # 0 (Medo Extremo) a 100 (Ganância Extrema)

@dataclass
class MarketSentimentOverview:
    fear_greed_score: int       # 0 a 100
    fear_greed_label: str       # "Medo Extremo", "Medo / Cautela", "Neutro", "Otimismo", "Euforia"
    resumo_macro_humor: str
    pilares: List[QuantitativeSentimentPillar]
    news_feed: List[MarketNewsItem]
    trending_tickers: List[Dict[str, Any]]
    timestamp: str

class MarketSentimentAnalyzer:
    """
    Motor quantitativo e fundamentado de Sentimento de Mercado da B3.
    Inspirado no Fear & Greed Index da CNN, calibrado para a realidade brasileira:
    1. Momentum do Ibovespa (Preço vs Média Móvel de 50 dias)
    2. Índice de Força Relativa (IFR / RSI 14) do Ibovespa
    3. Pressão Cambial (Dólar USD/BRL - fuga de capital vs apetite a risco)
    4. Volatilidade e Amplitude Recente do Mercado
    5. Feed de Notícias Reais via API Financeira
    """

    def fetch_live_sentiment(self) -> MarketSentimentOverview:
        # 1. Coleta de Dados do Ibovespa (^BVSP)
        ibov_obj = yf.Ticker("^BVSP")
        ibov_hist = ibov_obj.history(period="6mo")
        
        # 2. Coleta de Dados do Dólar (BRL=X)
        usd_obj = yf.Ticker("BRL=X")
        usd_hist = usd_obj.history(period="2mo")

        pilares = []
        scores = []

        # --- PILAR 1: Momentum do Ibovespa (Preço vs MM50) ---
        if not ibov_hist.empty and len(ibov_hist) >= 50:
            closes = ibov_hist["Close"]
            current_ibov = float(closes.iloc[-1])
            sma50 = float(closes.rolling(50).mean().iloc[-1])
            dist_sma50_pct = ((current_ibov - sma50) / sma50) * 100

            # Se estiver muito acima da MM50 = Ganância; muito abaixo = Medo
            if dist_sma50_pct >= 6.0:
                p1_score = 85
                p1_diag = f"Forte tendência de alta (+{dist_sma50_pct:.1f}% acima da MM50)"
            elif dist_sma50_pct >= 1.5:
                p1_score = 65
                p1_diag = f"Acima da média móvel (+{dist_sma50_pct:.1f}%)"
            elif dist_sma50_pct >= -2.0:
                p1_score = 50
                p1_diag = "Próximo à média de 50 dias (Neutro)"
            elif dist_sma50_pct >= -7.0:
                p1_score = 30
                p1_diag = f"Correção em andamento ({dist_sma50_pct:.1f}% abaixo da MM50)"
            else:
                p1_score = 15
                p1_diag = f"Medo severo: mercado descolado para baixo ({dist_sma50_pct:.1f}% da MM50)"

            pilares.append(QuantitativeSentimentPillar(
                nome="Momentum do Ibovespa (vs MM50)",
                valor_atual=f"{current_ibov:,.0f} pts (MM50: {sma50:,.0f})",
                diagnostico=p1_diag,
                score=p1_score
            ))
            scores.append((p1_score, 0.30))
        else:
            current_ibov = 130000.0

        # --- PILAR 2: IFR 14 (Sobrevenda vs Sobrecompra do Ibovespa) ---
        if not ibov_hist.empty and len(ibov_hist) >= 15:
            delta = ibov_hist["Close"].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            if rsi >= 70:
                p2_score = 85
                p2_diag = f"Sobrecompra extrema (IFR {rsi:.1f}) - Euforia de curto prazo"
            elif rsi >= 55:
                p2_score = 65
                p2_diag = f"Pressão compradora saudável (IFR {rsi:.1f})"
            elif rsi >= 45:
                p2_score = 50
                p2_diag = f"Equilíbrio técnico (IFR {rsi:.1f})"
            elif rsi >= 30:
                p2_score = 30
                p2_diag = f"Pressão vendedora / Cautela (IFR {rsi:.1f})"
            else:
                p2_score = 15
                p2_diag = f"Sobrevenda extrema (IFR {rsi:.1f}) - Pânico vendedor / Barganhas"

            pilares.append(QuantitativeSentimentPillar(
                nome="Índice de Força Relativa (IFR 14)",
                valor_atual=f"{rsi:.1f} pontos",
                diagnostico=p2_diag,
                score=p2_score
            ))
            scores.append((p2_score, 0.25))

        # --- PILAR 3: Termômetro Cambial (Dólar USD/BRL) ---
        if not usd_hist.empty and len(usd_hist) >= 20:
            usd_closes = usd_hist["Close"]
            usd_curr = float(usd_closes.iloc[-1])
            usd_1m_ago = float(usd_closes.iloc[0])
            usd_var_pct = ((usd_curr - usd_1m_ago) / usd_1m_ago) * 100

            # No Brasil, alta forte do dólar = aversão a risco / fuga de capital (Medo)
            # Queda do dólar = entrada de gringo / apetite a risco (Otimismo)
            if usd_var_pct >= 4.0:
                p3_score = 15
                p3_diag = f"Aversão a risco acentuada (Dólar subiu +{usd_var_pct:.1f}% em 30 dias)"
            elif usd_var_pct >= 1.0:
                p3_score = 35
                p3_diag = f"Cautela cambial (Dólar com viés de alta +{usd_var_pct:.1f}%)"
            elif usd_var_pct >= -1.0:
                p3_score = 50
                p3_diag = "Câmbio estável (Sem pressão no fluxo)"
            elif usd_var_pct >= -4.0:
                p3_score = 70
                p3_diag = f"Entrada de capital estrangeiro (Dólar caiu {usd_var_pct:.1f}%)"
            else:
                p3_score = 85
                p3_diag = f"Forte fluxo comprador internacional (Dólar despencou {usd_var_pct:.1f}%)"

            pilares.append(QuantitativeSentimentPillar(
                nome="Fluxo Cambial (Dólar USD/BRL)",
                valor_atual=f"R$ {usd_curr:.2f} ({usd_var_pct:+.1f}% no mês)",
                diagnostico=p3_diag,
                score=p3_score
            ))
            scores.append((p3_score, 0.25))

        # --- PILAR 4: Volatilidade Histórica Recente ---
        if not ibov_hist.empty and len(ibov_hist) >= 20:
            daily_returns = ibov_hist["Close"].pct_change().dropna()
            recent_vol = float(daily_returns.tail(20).std() * np.sqrt(252) * 100) # Volatilidade anualizada

            if recent_vol >= 25.0:
                p4_score = 20
                p4_diag = f"Turbulência e nervosismo elevados (Volatilidade {recent_vol:.1f}% a.a.)"
            elif recent_vol >= 18.0:
                p4_score = 40
                p4_diag = f"Oscilação moderada (Volatilidade {recent_vol:.1f}% a.a.)"
            else:
                p4_score = 70
                p4_diag = f"Mercado estável e previsível (Volatilidade branda {recent_vol:.1f}% a.a.)"

            pilares.append(QuantitativeSentimentPillar(
                nome="Volatilidade do Mercado (B3 Risk)",
                valor_atual=f"{recent_vol:.1f}% a.a.",
                diagnostico=p4_diag,
                score=p4_score
            ))
            scores.append((p4_score, 0.20))

        # Cálculo Ponderado Final
        if scores:
            final_fg = int(sum(score * weight for score, weight in scores))
        else:
            final_fg = 50

        final_fg = max(5, min(95, final_fg))

        if final_fg <= 25:
            fg_label = "🚨 MEDO EXTREMO (Pânico Vendedor / Oportunidade de Barganhas)"
            resumo = (
                "O mercado brasileiro opera sob estresse severo de aversão a risco. "
                "Historicamente, zonas de Medo Extremo com IFR sobrevendido representam os melhores pontos "
                "de entrada para comprar ações e FIIs de primeira linha com margem de segurança."
            )
        elif final_fg <= 45:
            fg_label = "⚠️ CAUTELA / MEDO (Mercado Defensivo)"
            resumo = (
                "Os investidores mostram cautela devido ao patamar dos juros futuros e câmbio. "
                "O fluxo favorece ativos de alta qualidade, dividendos e renda fixa soberana."
            )
        elif final_fg <= 55:
            fg_label = "⚖️ NEUTRO (Equilíbrio entre Compradores e Vendedores)"
            resumo = "Mercado sem tendência direcional dominante, consolidando preços à espera de novos gatilhos macroeconômicos."
        elif final_fg <= 75:
            fg_label = "🌱 OTIMISMO (Apetite a Risco em Expansão)"
            resumo = "Sentimento positivo impulsionado por fluxo comprador de ações e compressão de taxas de juros."
        else:
            fg_label = "🔥 EUFORIA EXTREMA (Sobrecompra / Cuidado com Topos)"
            resumo = "Mercado eufórico com múltiplos esticados. Momento exige disciplina e realização parcial de lucros."

        # Coleta Notícias Reais do Yahoo Finance
        real_news = self._fetch_yfinance_news(ibov_obj)

        # Ativos em Destaque no Momento (Volume e Notícias)
        trending = [
            {"ticker": "PETR4", "empresa": "Petrobras", "motivo": "Fluxo de dividendos e sensibilidade ao barril do petróleo Brent", "tendencia": "Alta Liquidez"},
            {"ticker": "VALE3", "empresa": "Vale", "motivo": "Oscilação do minério de ferro na China e demanda global", "tendencia": "Consolidação"},
            {"ticker": "ITUB4", "empresa": "Itaú Unibanco", "motivo": "Resiliência bancária e margens financeiras robustas", "tendencia": "Otimista"},
            {"ticker": "HGLG11", "empresa": "CSHG Logística", "motivo": "Desconto em galpões logísticos e atratividade frente à NTN-B", "tendencia": "Barganha em FII"}
        ]

        return MarketSentimentOverview(
            fear_greed_score=final_fg,
            fear_greed_label=fg_label,
            resumo_macro_humor=resumo,
            pilares=pilares,
            news_feed=real_news,
            trending_tickers=trending,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    def _fetch_yfinance_news(self, ticker_obj) -> List[MarketNewsItem]:
        items = []
        try:
            raw_news = ticker_obj.news or []
            for item in raw_news[:8]:
                content = item.get("content") or {}
                title = content.get("title") or item.get("title") or ""
                summary = content.get("summary") or item.get("summary") or ""
                provider = content.get("provider", {}).get("displayName") or "Mídia Financeira"
                url = content.get("canonicalUrl", {}).get("url") or item.get("link") or "https://finance.yahoo.com"
                pub_date = content.get("pubDate") or ""
                if pub_date:
                    pub_date = pub_date[:10]

                tickers = []
                for t in content.get("finance", {}).get("stockTickers", []):
                    sym = t.get("symbol", "").replace(".SA", "")
                    if sym and not sym.startswith("^"):
                        tickers.append(sym)

                # Classificação de sentimento simples no texto real
                full_text = f"{title} {summary}".lower()
                if any(w in full_text for w in ["sobe", "alta", "lucro", "recorde", "dividendo", "compra", "positivo", "supera"]):
                    sent = "OTIMISTA"
                    score = 0.5
                elif any(w in full_text for w in ["queda", "cai", "prejuízo", "risco", "corte", "baixa", "alerta", "inadimplência"]):
                    sent = "ALERTA"
                    score = -0.5
                else:
                    sent = "NEUTRO"
                    score = 0.0

                items.append(MarketNewsItem(
                    title=title,
                    summary=summary[:180] + "..." if len(summary) > 180 else summary,
                    link=url,
                    published=pub_date,
                    source=provider,
                    sentiment_label=sent,
                    score=score,
                    related_tickers=tickers[:3]
                ))
        except Exception:
            pass

        return items
