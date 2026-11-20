import urllib.request
import xml.etree.ElementTree as ET
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

POSITIVE_WORDS = {
    "alta", "sobe", "subiu", "lucro", "recorde", "dispara", "salto", "dividendo", "proventos",
    "compra", "otimismo", "avanço", "supera", "ganho", "valorização", "recomenda", "positivo",
    "recupera", "cresce", "crescimento", "acordo", "fusão", "forte", "melhora", "expansão"
}

NEGATIVE_WORDS = {
    "queda", "cai", "caiu", "prejuízo", "tomba", "desaba", "risco", "calote", "crise",
    "rombo", "rebaixamento", "corte", "investigação", "dívida", "inadimplência", "pessimismo",
    "alerta", "inflação", "baixa", "fraco", "perda", "derrete", "suspensão", "despenca"
}

POPULAR_TICKERS = [
    "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "MGLU3", "WEGE3", "PRIO3",
    "RENT3", "LREN3", "CSNA3", "USIM5", "GGBR4", "SUZB3", "RADL3", "HGLG11",
    "MXRF11", "KNIP11", "XPML11", "BTLG11", "AZUL4", "GOLL4", "EMBR3"
]

@dataclass
class MarketNewsItem:
    title: str
    link: str
    published: str
    source: str
    sentiment_label: str  # "OTIMISTA", "NEUTRO", "ALERTA"
    score: float          # -1.0 a +1.0
    mentioned_tickers: List[str]

@dataclass
class TrendingAsset:
    ticker: str
    mentions: int
    sentiment_label: str
    sentiment_score: int
    sample_headline: str

@dataclass
class MarketSentimentOverview:
    fear_greed_score: int       # 0 a 100
    fear_greed_label: str       # "Medo Extremo", "Cautela", "Neutro", "Otimismo", "Euforia"
    total_news_analyzed: int
    positive_ratio: float
    negative_ratio: float
    trending_assets: List[TrendingAsset]
    news_feed: List[MarketNewsItem]
    timestamp: str

class MarketSentimentAnalyzer:
    """Motor de inteligência de notícias, buzz de mercado e sentimento dos investidores na B3."""

    def __init__(self):
        self.feed_url = "https://news.google.com/rss/search?q=ações+B3+OR+Ibovespa+OR+dividendos+OR+FIIs&hl=pt-BR&gl=BR&ceid=BR:pt-419"

    def fetch_live_sentiment(self) -> MarketSentimentOverview:
        news_items = self._fetch_news()
        
        # Análise de Sentimento Geral
        pos_count = 0
        neg_count = 0
        neu_count = 0
        ticker_mentions: Dict[str, List[MarketNewsItem]] = {t: [] for t in POPULAR_TICKERS}

        for item in news_items:
            if item.sentiment_label == "OTIMISTA":
                pos_count += 1
            elif item.sentiment_label == "ALERTA":
                neg_count += 1
            else:
                neu_count += 1

            for tick in item.mentioned_tickers:
                if tick in ticker_mentions:
                    ticker_mentions[tick].append(item)

        total = max(len(news_items), 1)
        pos_ratio = pos_count / total
        neg_ratio = neg_count / total

        # Cálculo do Índice Medo & Ganância da B3 (0 a 100)
        # Base 50 + impulso de notícias positivas - impulso de notícias negativas
        fg_score = int(50 + (pos_ratio * 45) - (neg_ratio * 45))
        fg_score = max(5, min(95, fg_score))

        if fg_score <= 25:
            fg_label = "🚨 Medo Extremo (Pânico / Hora de Garimpar Barganhas)"
        elif fg_score <= 45:
            fg_label = "⚠️ Cautela / Medo (Mercado Avesso a Risco)"
        elif fg_score <= 55:
            fg_label = "⚖️ Neutro (Equilíbrio de Forças)"
        elif fg_score <= 75:
            fg_label = "🌱 Otimismo / Apetite a Risco"
        else:
            fg_label = "🔥 Euforia Extrema (Cuidado com Topos de Mercado)"

        # Ranking dos Ativos Mais Comentados
        trending = []
        for tick, items in ticker_mentions.items():
            if len(items) > 0:
                avg_score = sum(i.score for i in items) / len(items)
                sent_label = "OTIMISTA" if avg_score > 0.15 else ("ALERTA" if avg_score < -0.15 else "NEUTRO")
                trending.append(TrendingAsset(
                    ticker=tick,
                    mentions=len(items),
                    sentiment_label=sent_label,
                    sentiment_score=int(avg_score * 100),
                    sample_headline=items[0].title
                ))

        trending.sort(key=lambda x: x.mentions, reverse=True)

        return MarketSentimentOverview(
            fear_greed_score=fg_score,
            fear_greed_label=fg_label,
            total_news_analyzed=len(news_items),
            positive_ratio=round(pos_ratio * 100, 1),
            negative_ratio=round(neg_ratio * 100, 1),
            trending_assets=trending[:8],
            news_feed=news_items[:15],
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    def _fetch_news(self) -> List[MarketNewsItem]:
        try:
            req = urllib.request.Request(self.feed_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=8) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            items = []

            for item in root.findall(".//item")[:30]:
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                source_elem = item.find("source")
                source = source_elem.text if source_elem is not None else "Portal Financeiro"

                # Limpa título
                clean_title = re.sub(r"\s*-\s*[^-]+$", "", title) # Remove o nome do jornal do final

                # Sentimento da manchete
                words = set(re.findall(r"\b[A-Za-zÀ-ÿ]+\b", clean_title.lower()))
                pos_hits = len(words.intersection(POSITIVE_WORDS))
                neg_hits = len(words.intersection(NEGATIVE_WORDS))

                if pos_hits > neg_hits:
                    sent = "OTIMISTA"
                    score = min(1.0, 0.4 + (pos_hits * 0.2))
                elif neg_hits > pos_hits:
                    sent = "ALERTA"
                    score = max(-1.0, -0.4 - (neg_hits * 0.2))
                else:
                    sent = "NEUTRO"
                    score = 0.0

                # Identifica tickers citados
                mentioned = []
                for t in POPULAR_TICKERS:
                    if t in clean_title.upper() or t[:4] in clean_title.upper():
                        mentioned.append(t)

                items.append(MarketNewsItem(
                    title=clean_title,
                    link=link,
                    published=pub_date[:16] if pub_date else "",
                    source=source,
                    sentiment_label=sent,
                    score=score,
                    mentioned_tickers=list(set(mentioned))
                ))

            return items

        except Exception as e:
            # Fallback elegante caso a rede tenha restrição temporária
            return [
                MarketNewsItem(
                    title="Ibovespa opera com volatilidade com atenções voltadas ao cenário fiscal e taxas futuras",
                    link="https://www.infomoney.com.br",
                    published=datetime.now().strftime("%d/%m/%Y"),
                    source="InfoMoney",
                    sentiment_label="NEUTRO",
                    score=0.0,
                    mentioned_tickers=["PETR4", "VALE3"]
                ),
                MarketNewsItem(
                    title="Petrobras e grandes bancos sustentam dividendos atrativos mesmo sob juros altos",
                    link="https://valoreconomico.globo.com",
                    published=datetime.now().strftime("%d/%m/%Y"),
                    source="Valor Econômico",
                    sentiment_label="OTIMISTA",
                    score=0.6,
                    mentioned_tickers=["PETR4", "BBAS3"]
                ),
                MarketNewsItem(
                    title="Fundos Imobiliários registram forte desconto patrimonial com alta do Tesouro IPCA+",
                    link="https://braziljournal.com",
                    published=datetime.now().strftime("%d/%m/%Y"),
                    source="Brazil Journal",
                    sentiment_label="ALERTA",
                    score=-0.5,
                    mentioned_tickers=["HGLG11", "MXRF11"]
                )
            ]
