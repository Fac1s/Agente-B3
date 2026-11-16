import streamlit as st
import pandas as pd
from datetime import datetime

from models import StockData, AnalysisVerdict, AnalysisReport
from data_fetcher import fetch_b3_stock
from analyst import B3StockAnalyst
from screener import B3MarketScreener, get_universe_by_name

# Configuração da Página
st.set_page_config(
    page_title="Analista B3 - Inteligência de Mercado",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização Customizada
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E88E5;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #888888;
        margin-bottom: 25px;
    }
    .verdict-compra {
        background-color: #1B5E20;
        color: #FFFFFF;
        padding: 6px 14px;
        border-radius: 8px;
        font-weight: bold;
        display: inline-block;
    }
    .verdict-manter {
        background-color: #E65100;
        color: #FFFFFF;
        padding: 6px 14px;
        border-radius: 8px;
        font-weight: bold;
        display: inline-block;
    }
    .verdict-venda {
        background-color: #B71C1C;
        color: #FFFFFF;
        padding: 6px 14px;
        border-radius: 8px;
        font-weight: bold;
        display: inline-block;
    }
    .metric-box {
        background-color: #1E222D;
        border: 1px solid #2A2E39;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Cache de dados para respostas ultrarrápidas
@st.cache_data(ttl=600, show_spinner=False)
def get_cached_stock(ticker: str):
    return fetch_b3_stock(ticker)

@st.cache_data(ttl=900, show_spinner=False)
def run_cached_scan(universe_name: str, top_n: int):
    screener = B3MarketScreener(universe=universe_name, max_workers=10)
    return screener.scan_market(top_n=top_n)

# Barra Lateral
st.sidebar.title("📈 Analista B3")
st.sidebar.caption("Inteligência Fundamentalista & Anti-Alucinação")
st.sidebar.divider()

modo = st.sidebar.radio(
    "Navegação:",
    ["🎯 Varredura de Mercado (Deep Value)", "🔍 Raio-X de Ativo Específico"],
    index=0
)

st.sidebar.divider()
st.sidebar.info(
    "💡 **Sobre o Agente:** Analisa ações da B3 através de regras fundamentalistas, "
    "sensibilidade macroeconômica local (Selic) e camada ativa de **Fact-Checking** contra números falsos."
)

# -----------------------------------------------------------------------------
# MODO 1: VARREDURA GERAL DE MERCADO
# -----------------------------------------------------------------------------
if modo == "🎯 Varredura de Mercado (Deep Value)":
    st.markdown('<div class="main-header">🎯 Varredura de Oportunidades na B3</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Garimpe ações com desconto severo de múltiplos, balanço sólido e assimetria favorável.</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        universo = st.selectbox(
            "Selecione o Universo de Ações:",
            ["ibov", "smallcaps", "dividendos", "all"],
            format_func=lambda x: {
                "ibov": "Ibovespa Completo (80+ maiores ações)",
                "smallcaps": "Small Caps (Empresas menores com alto potencial)",
                "dividendos": "Dividendos (Maiores geradoras de caixa / IDIV)",
                "all": "Bolsa Completa (110+ ações líquidas)"
            }[x]
        )
    with col2:
        top_n = st.slider("Quantidade no Ranking:", min_value=3, max_value=15, value=5)
    with col3:
        st.write("")
        st.write("")
        btn_scan = st.button("🚀 Iniciar Varredura", use_container_width=True, type="primary")

    if btn_scan or "last_scan" in st.session_state:
        if btn_scan:
            with st.spinner(f"Varrendo ações em tempo real via multi-threading... Aguarde!"):
                report = run_cached_scan(universo, top_n)
                st.session_state["last_scan"] = report
        else:
            report = st.session_state["last_scan"]

        st.success(f"Varredura concluída! {report.analyzed_count} de {report.universe_size} ativos analisados com sucesso.")

        # Monta a tabela interativa
        table_data = []
        for i, opp in enumerate(report.top_opportunities, 1):
            table_data.append({
                "Ranking": f"#{i}",
                "Ticker": opp.ticker,
                "Empresa": opp.company_name,
                "Setor": opp.sector,
                "Preço (R$)": f"R$ {opp.current_price:.2f}",
                "P/L": f"{opp.pe_ratio:.1f}x" if opp.pe_ratio else "N/A",
                "P/VP": f"{opp.pb_ratio:.2f}x" if opp.pb_ratio else "N/A",
                "ROE": f"{opp.roe:.1f}%" if opp.roe else "N/A",
                "DY": f"{opp.dividend_yield:.1f}%" if opp.dividend_yield else "0.0%",
                "IFR 14": f"{opp.rsi_14:.1f}" if opp.rsi_14 else "N/A",
                "Upside Score": f"{opp.total_upside_score} / 100"
            })

        df_ranking = pd.DataFrame(table_data)
        st.dataframe(df_ranking, use_container_width=True, hide_index=True)

        st.subheader("🔍 Detalhamento das Teses de Reprecificação")
        for i, opp in enumerate(report.top_opportunities, 1):
            with st.expander(f"#{i} - {opp.ticker} ({opp.company_name}) | Score: {opp.total_upside_score}/100"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Preço Atual", f"R$ {opp.current_price:.2f}")
                c2.metric("Score de Desconto", f"{opp.deep_value_score}/100")
                c3.metric("Score de Qualidade", f"{opp.quality_score}/100")
                c4.metric("Score Catalisador", f"{opp.catalyst_score}/100")
                
                st.write(f"**Tese Central:** {opp.primary_thesis.capitalize()}.")

# -----------------------------------------------------------------------------
# MODO 2: RAIO-X INDIVIDUAL DE UMA AÇÃO
# -----------------------------------------------------------------------------
else:
    st.markdown('<div class="main-header">🔍 Raio-X Fundamentalista & Fact-Checking</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Insira o código de qualquer ação da B3 para gerar a tese completa auditada.</div>', unsafe_allow_html=True)

    col_input, col_btn = st.columns([3, 1])
    with col_input:
        ticker_input = st.text_input("Código do Ticker (ex: PETR4, VALE3, ITUB4, WEGE3):", value="PETR4").upper().strip()
    with col_btn:
        st.write("")
        st.write("")
        btn_analisar = st.button("📊 Analisar Ativo", use_container_width=True, type="primary")

    if ticker_input:
        try:
            with st.spinner(f"Coletando dados cadastrais, múltiplos e balanço de {ticker_input}..."):
                stock_data = get_cached_stock(ticker_input)
                analyst = B3StockAnalyst(stock_data)
                rep: AnalysisReport = analyst.generate_report()

            # Cabeçalho do Ativo
            st.divider()
            h_col1, h_col2, h_col3 = st.columns([2, 1, 1])
            with h_col1:
                st.markdown(f"### {rep.ticker} - {rep.company_name}")
                st.caption(f"Setor: {rep.sector} | Cotação: R$ {rep.ground_truth_data.get('current_price', 0):.2f}")
            with h_col2:
                v_class = f"verdict-{rep.verdict.value.lower()}"
                st.markdown(f"**Veredito do Agente:**")
                st.markdown(f'<span class="{v_class}">{rep.verdict.value}</span>', unsafe_allow_html=True)
            with h_col3:
                st.metric("Score Fundamentalista", f"{rep.fundamental_score} / 100")

            # Métrica Cards
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("P/L", f"{rep.ground_truth_data.get('pe_ratio') or 'N/A'}")
            m2.metric("P/VP", f"{rep.ground_truth_data.get('pb_ratio') or 'N/A'}")
            m3.metric("EV/EBITDA", f"{rep.ground_truth_data.get('ev_ebitda') or 'N/A'}")
            m4.metric("Dividend Yield", f"{rep.ground_truth_data.get('dividend_yield', 0):.2f}%")
            m5.metric("ROE", f"{rep.ground_truth_data.get('roe') or 'N/A'}%")
            m6.metric("IFR 14 (RSI)", f"{rep.ground_truth_data.get('rsi_14') or 'N/A'}")

            st.divider()

            # Resumos
            st.markdown("#### 📊 Avaliação de Valuation")
            st.write(rep.valuation_summary)

            st.markdown("#### 🏥 Saúde Financeira & Solvência")
            st.write(rep.financial_health_summary)

            st.markdown("#### 🌎 Sensibilidade Macroeconômica (Cenário Brasil)")
            st.info(rep.macro_sensitivity)

            col_cat, col_risk = st.columns(2)
            with col_cat:
                st.markdown("#### 🚀 Principais Catalisadores")
                for c in rep.key_catalysts:
                    st.write(f"• {c}")
            with col_risk:
                st.markdown("#### ⚠️ Fatores de Risco")
                for r in rep.key_risks:
                    st.write(f"• {r}")

            # Painel de Auditoria de Fact-Checking
            with st.expander("🛡️ Auditoria de Validação do Agente (Anti-Alucinação)", expanded=True):
                v = rep.validation
                if v.is_valid:
                    st.success("✅ Relatório APROVADO: Todos os números citados no texto foram validados com os dados oficiais.")
                else:
                    st.error("❌ Alerta de Validação: Foram identificadas inconsistências.")

                for p in v.passed_checks:
                    st.write(f"✓ {p}")
                if v.warnings:
                    for w in v.warnings:
                        st.warning(f"Aviso: {w}")

        except Exception as e:
            st.error(f"Erro ao analisar o ativo {ticker_input}: {e}")
