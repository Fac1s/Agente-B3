import streamlit as st
import pandas as pd
from datetime import datetime

from models import StockData, AnalysisVerdict, AnalysisReport
from data_fetcher import fetch_b3_stock
from analyst import B3StockAnalyst
from screener import B3MarketScreener, get_universe_by_name
from fixed_income_analyst import FixedIncomeAnalyst, MacroEconomicContext
from fii_analyst import FIIAnalyst, FII_METADATA
from sentiment_analyzer import MarketSentimentAnalyzer, MarketSentimentOverview

# Configuração da Página
st.set_page_config(
    page_title="Analista B3 - Inteligência de Mercado Multi-Ativos",
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
    .verdict-compra, .verdict-forte-compra, .badge-otimista {
        background-color: #1B5E20;
        color: #FFFFFF;
        padding: 5px 12px;
        border-radius: 8px;
        font-weight: bold;
        display: inline-block;
        font-size: 0.9rem;
    }
    .verdict-manter, .verdict-neutro, .badge-neutro {
        background-color: #E65100;
        color: #FFFFFF;
        padding: 5px 12px;
        border-radius: 8px;
        font-weight: bold;
        display: inline-block;
        font-size: 0.9rem;
    }
    .verdict-venda, .verdict-evitar, .verdict-cuidado---evitar, .badge-alerta {
        background-color: #B71C1C;
        color: #FFFFFF;
        padding: 5px 12px;
        border-radius: 8px;
        font-weight: bold;
        display: inline-block;
        font-size: 0.9rem;
    }
    .news-card {
        background-color: #1E222D;
        border: 1px solid #2A2E39;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Cache de dados para performance rápida
@st.cache_data(ttl=600, show_spinner=False)
def get_cached_stock(ticker: str):
    return fetch_b3_stock(ticker)

@st.cache_data(ttl=900, show_spinner=False)
def run_cached_scan(universe_name: str, top_n: int):
    screener = B3MarketScreener(universe=universe_name, max_workers=10)
    return screener.scan_market(top_n=top_n)

@st.cache_data(ttl=600, show_spinner=False)
def get_cached_fii(ticker: str):
    analyst = FIIAnalyst()
    return analyst.fetch_fii_data(ticker)

@st.cache_data(ttl=900, show_spinner=False)
def run_cached_fii_scan(top_n: int, apenas_barganhas: bool):
    analyst = FIIAnalyst()
    return analyst.scan_fiis(top_n=top_n, apenas_barganhas=apenas_barganhas)

@st.cache_data(ttl=300, show_spinner=False)
def get_cached_sentiment():
    analyzer = MarketSentimentAnalyzer()
    return analyzer.fetch_live_sentiment()

# Barra Lateral
st.sidebar.title("📈 Analista B3 Multi-Ativos")
st.sidebar.caption("Inteligência Fundamentalista, FIIs e Sentimento")
st.sidebar.divider()

modo = st.sidebar.radio(
    "Navegação Principal:",
    [
        "🎯 Varredura de Ações (Deep Value)",
        "🔍 Raio-X de Ação Individual",
        "🏢 Fundos Imobiliários (FIIs - Barganhas & Spreads)",
        "🏛️ Renda Fixa & Títulos Públicos (Tesouro)",
        "🔥 Sentimento de Mercado & Trending (B3)"
    ],
    index=0
)

st.sidebar.divider()
st.sidebar.info(
    "💡 **Recursos do Agente:**\n"
    "• **Ações:** Desconto de múltiplos, balanço e anti-alucinação.\n"
    "• **FIIs:** P/VP, spread vs NTN-B e filtro anti-ciladas.\n"
    "• **Renda Fixa:** Taxa real IPCA+ e simulador líquido.\n"
    "• **Sentimento:** Índice de Medo & Ganância e ativos em alta."
)

# -----------------------------------------------------------------------------
# MODO 1: VARREDURA GERAL DE AÇÕES (DEEP VALUE)
# -----------------------------------------------------------------------------
if modo == "🎯 Varredura de Ações (Deep Value)":
    st.markdown('<div class="main-header">🎯 Varredura de Oportunidades em Ações</div>', unsafe_allow_html=True)
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
elif modo == "🔍 Raio-X de Ação Individual":
    st.markdown('<div class="main-header">🔍 Raio-X Fundamentalista de Ação</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Insira o código de qualquer ação da B3 para gerar a tese completa auditada.</div>', unsafe_allow_html=True)

    col_input, col_btn = st.columns([3, 1])
    with col_input:
        ticker_input = st.text_input("Código do Ticker (ex: PETR4, VALE3, ITUB4, WEGE3):", value="PETR4").upper().strip()
    with col_btn:
        st.write("")
        st.write("")
        btn_analisar = st.button("📊 Analisar Ação", use_container_width=True, type="primary")

    if ticker_input:
        try:
            with st.spinner(f"Coletando dados cadastrais, múltiplos e balanço de {ticker_input}..."):
                stock_data = get_cached_stock(ticker_input)
                analyst = B3StockAnalyst(stock_data)
                rep: AnalysisReport = analyst.generate_report()

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

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("P/L", f"{rep.ground_truth_data.get('pe_ratio') or 'N/A'}")
            m2.metric("P/VP", f"{rep.ground_truth_data.get('pb_ratio') or 'N/A'}")
            m3.metric("EV/EBITDA", f"{rep.ground_truth_data.get('ev_ebitda') or 'N/A'}")
            m4.metric("Dividend Yield", f"{rep.ground_truth_data.get('dividend_yield', 0):.2f}%")
            m5.metric("ROE", f"{rep.ground_truth_data.get('roe') or 'N/A'}%")
            m6.metric("IFR 14 (RSI)", f"{rep.ground_truth_data.get('rsi_14') or 'N/A'}")

            st.divider()
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
            st.error(f"Erro ao analisar a ação {ticker_input}: {e}")

# -----------------------------------------------------------------------------
# MODO 3: FUNDOS IMOBILIÁRIOS (FIIS - AVALIAÇÃO DE DESCONTO AVANÇADA)
# -----------------------------------------------------------------------------
elif modo == "🏢 Fundos Imobiliários (FIIs - Barganhas & Spreads)":
    st.markdown('<div class="main-header">🏢 Fundos Imobiliários: Garimpo de Barganhas & Spreads</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Identifique ativos com desconto patrimonial real, prêmio sobre o Tesouro IPCA+ e expurgo de armadilhas.</div>', unsafe_allow_html=True)

    sub_fii = st.radio("Selecione a Ferramenta de FIIs:", ["🏆 Varredura dos Maiores FIIs do IFIX", "🔍 Raio-X Detalhado de FII"], horizontal=True)

    if sub_fii == "🏆 Varredura dos Maiores FIIs do IFIX":
        col_fii_cfg1, col_fii_cfg2, col_fii_cfg3 = st.columns([2, 1, 1])
        with col_fii_cfg1:
            apenas_barganhas = st.checkbox("🛡️ Ocultar Armadilhas de Valor (Exibir apenas Barganhas Reais)", value=True)
        with col_fii_cfg2:
            top_fii_n = st.slider("Qtd. de Fundos:", min_value=5, max_value=20, value=10)
        with col_fii_cfg3:
            btn_scan_fii = st.button("🚀 Escanear FIIs", type="primary", use_container_width=True)

        if btn_scan_fii or "last_fii_scan" in st.session_state:
            if btn_scan_fii:
                with st.spinner("Analisando FIIs, spreads vs NTN-B e diagnóstico de desconto..."):
                    top_fiis = run_cached_fii_scan(top_n=top_fii_n, apenas_barganhas=apenas_barganhas)
                    st.session_state["last_fii_scan"] = top_fiis
            else:
                top_fiis = st.session_state["last_fii_scan"]

            fii_table = []
            for i, f in enumerate(top_fiis, 1):
                fii_table.append({
                    "Ranking": f"#{i}",
                    "Ticker": f.ticker,
                    "Nome": f.nome,
                    "Segmento": f.segmento,
                    "Cotação": f"R$ {f.preco_atual:.2f}",
                    "P/VP": f"{f.pvp:.2f}x" if f.pvp else "N/A",
                    "DY Anual": f"{f.dividend_yield_anual:.1f}%",
                    "Rend. Mensal Isento": f"~{f.rendimento_mensal_estimado:.2f}% a.m.",
                    "Spread vs NTN-B": f"+{f.spread_vs_ntnb:.1f}% a.a." if f.spread_vs_ntnb >= 0 else f"{f.spread_vs_ntnb:.1f}%",
                    "Diagnóstico": f.diagnostico_desconto,
                    "Score FII": f"{f.score_fii} / 100"
                })
            st.dataframe(pd.DataFrame(fii_table), use_container_width=True, hide_index=True)

            st.caption("📌 **Nota:** O *Spread vs NTN-B* calcula quanto o rendimento isento do FII supera a taxa de juros real do Tesouro IPCA+ longo (referência 6,70% a.a.).")

    else:
        fii_col_in, fii_col_bt = st.columns([3, 1])
        with fii_col_in:
            fii_ticker = st.text_input("Código do FII (ex: HGLG11, BTLG11, KNIP11, MXRF11, XPML11, HGRU11):", value="HGLG11").upper().strip()
        with fii_col_bt:
            st.write("")
            st.write("")
            btn_fii = st.button("📊 Analisar FII", use_container_width=True, type="primary")

        if fii_ticker:
            try:
                with st.spinner(f"Coletando cotas, múltiplos e proventos de {fii_ticker}..."):
                    fii_data = get_cached_fii(fii_ticker)

                st.divider()
                fh1, fh2, fh3 = st.columns([2, 1, 1])
                with fh1:
                    st.markdown(f"### {fii_data.ticker} - {fii_data.nome}")
                    st.caption(f"Segmento: {fii_data.segmento} | Perfil: {fii_data.perfil}")
                with fh2:
                    f_class = f"verdict-{fii_data.veredito.lower().replace(' ', '-').replace('/', '-')}"
                    st.markdown(f"**Veredito do Agente:**")
                    st.markdown(f'<span class="{f_class}">{fii_data.veredito}</span>', unsafe_allow_html=True)
                with fh3:
                    st.metric("Score do FII", f"{fii_data.score_fii} / 100")

                # Métricas Chave
                fm1, fm2, fm3, fm4, fm5 = st.columns(5)
                fm1.metric("Cotação Atual", f"R$ {fii_data.preco_atual:.2f}")
                fm2.metric("P/VP", f"{fii_data.pvp:.2f}x" if fii_data.pvp else "N/A")
                fm3.metric("DY Anualizado", f"{fii_data.dividend_yield_anual:.1f}%")
                fm4.metric("Rend. Bruto Equiv.", f"{fii_data.rendimento_bruto_equivalente:.1f}% a.a.")
                fm5.metric("Spread vs NTN-B", f"+{fii_data.spread_vs_ntnb:.1f}% a.a." if fii_data.spread_vs_ntnb >= 0 else f"{fii_data.spread_vs_ntnb:.1f}%")

                st.info(f"**Diagnóstico de Desconto do FII:** {fii_data.diagnostico_desconto}")

                st.divider()
                st.markdown("#### 🎯 Tese de Investimento do Agente")
                st.write(fii_data.tese)

                fc1, fc2 = st.columns(2)
                with fc1:
                    st.markdown("#### 🚀 Catalisadores & Margem de Segurança")
                    for c in fii_data.catalisadores:
                        st.write(f"• {c}")
                with fc2:
                    st.markdown("#### ⚠️ Riscos do FII (Vacância, Dívida & Juros)")
                    for r in fii_data.riscos:
                        st.write(f"• {r}")

            except Exception as e:
                st.error(f"Erro ao analisar o FII {fii_ticker}: {e}")

# -----------------------------------------------------------------------------
# MODO 4: RENDA FIXA & TÍTULOS PÚBLICOS (TESOURO DIRETO)
# -----------------------------------------------------------------------------
elif modo == "🏛️ Renda Fixa & Títulos Públicos (Tesouro)":
    st.markdown('<div class="main-header">🏛️ Renda Fixa Soberana & Títulos Públicos</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Análise macroeconômica, curva de juros do Brasil e alocação estratégica no Tesouro Direto.</div>', unsafe_allow_html=True)

    rf_engine = FixedIncomeAnalyst()
    macro = rf_engine.macro

    st.markdown("### 📊 Termômetro Macroeconômico Atual do Brasil")
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("Taxa Selic Meta", f"{macro.selic_meta:.2f}% a.a.")
    mc2.metric("IPCA Acumulado 12M", f"{macro.ipca_12m:.2f}%")
    mc3.metric("Inflação Focus Proj.", f"{macro.ipca_focus_proj:.2f}%")
    mc4.metric("DI Futuro 5 Anos", f"{macro.di_5y:.2f}%")
    mc5.metric("Risco Fiscal", macro.risco_fiscal_status)

    st.divider()
    st.markdown("### 🎯 Avaliação e Vereditos dos Títulos Públicos")

    selic_bond = rf_engine.analyze_tesouro_selic()
    ipca_bond = rf_engine.analyze_tesouro_ipca()
    pre_bond = rf_engine.analyze_tesouro_prefixado()

    t_tab1, t_tab2, t_tab3 = st.tabs(["🔒 Tesouro IPCA+ (Juro Real)", "💰 Tesouro Selic (Pós-Fixado)", "⏳ Tesouro Prefixado"])

    with t_tab1:
        st.subheader(f"{ipca_bond.nome_titulo} — Taxa: {ipca_bond.taxa_indicativa}")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Veredito:** <span class='verdict-forte-compra'>{ipca_bond.veredito}</span>", unsafe_allow_html=True)
        c2.metric("Score de Atratividade", f"{ipca_bond.score_atratividade} / 100")
        c3.metric("Risco de Marcação a Mercado", ipca_bond.marcação_a_mercado)

        st.info(f"**Tese Macroeconômica:** {ipca_bond.tese_macro}")
        st.write(f"**Indicado para:** {ipca_bond.indicado_para}")

        ca1, ca2 = st.columns(2)
        with ca1:
            st.markdown("#### ✅ Vantagens Estratégicas")
            for v in ipca_bond.principais_vantagens:
                st.write(f"• {v}")
        with ca2:
            st.markdown("#### ⚠️ Riscos e Cuidados")
            for r in ipca_bond.principais_riscos:
                st.write(f"• {r}")

    with t_tab2:
        st.subheader(f"{selic_bond.nome_titulo} — Taxa: {selic_bond.taxa_indicativa}")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Veredito:** <span class='verdict-compra'>{selic_bond.veredito}</span>", unsafe_allow_html=True)
        c2.metric("Score de Atratividade", f"{selic_bond.score_atratividade} / 100")
        c3.metric("Risco de Marcação a Mercado", selic_bond.marcação_a_mercado)

        st.info(f"**Tese Macroeconômica:** {selic_bond.tese_macro}")
        st.write(f"**Indicado para:** {selic_bond.indicado_para}")

        ca1, ca2 = st.columns(2)
        with ca1:
            st.markdown("#### ✅ Vantagens Estratégicas")
            for v in selic_bond.principais_vantagens:
                st.write(f"• {v}")
        with ca2:
            st.markdown("#### ⚠️ Riscos e Cuidados")
            for r in selic_bond.principais_riscos:
                st.write(f"• {r}")

    with t_tab3:
        st.subheader(f"{pre_bond.nome_titulo} — Taxa: {pre_bond.taxa_indicativa}")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Veredito:** <span class='verdict-manter'>{pre_bond.veredito}</span>", unsafe_allow_html=True)
        c2.metric("Score de Atratividade", f"{pre_bond.score_atratividade} / 100")
        c3.metric("Risco de Marcação a Mercado", pre_bond.marcação_a_mercado)

        st.info(f"**Tese Macroeconômica:** {pre_bond.tese_macro}")
        st.write(f"**Indicado para:** {pre_bond.indicado_para}")

        ca1, ca2 = st.columns(2)
        with ca1:
            st.markdown("#### ✅ Vantagens Estratégicas")
            for v in pre_bond.principais_vantagens:
                st.write(f"• {v}")
        with ca2:
            st.markdown("#### ⚠️ Riscos e Cuidados")
            for r in pre_bond.principais_riscos:
                st.write(f"• {r}")

    st.divider()
    st.markdown("### 🧮 Simulador de Rentabilidade Líquida (Após IR)")
    sim_col1, sim_col2 = st.columns([1, 1])
    with sim_col1:
        val_aporte = st.number_input("Valor do Aporte Inicial (R$):", min_value=500.0, max_value=1_000_000.0, value=10000.0, step=500.0)
    with sim_col2:
        val_prazo = st.slider("Prazo de Investimento (em anos):", min_value=1, max_value=15, value=5)

    sim_res = rf_engine.simulate_investment(val_aporte, val_prazo)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Tesouro IPCA+ (Líquido)", f"R$ {sim_res['tesouro_ipca']:,.2f}", delta="Maior Proteção Real")
    s2.metric("Tesouro Selic (Líquido)", f"R$ {sim_res['tesouro_selic']:,.2f}")
    s3.metric("Tesouro Prefixado (Líquido)", f"R$ {sim_res['tesouro_prefixado']:,.2f}")
    s4.metric("Poupança (Isenta)", f"R$ {sim_res['poupanca']:,.2f}", delta=f"-R$ {sim_res['ganho_extra_vs_poupanca']:,.2f}", delta_color="inverse")

# -----------------------------------------------------------------------------
# MODO 5: SENTIMENTO DE MERCADO & TRENDING (B3)
# -----------------------------------------------------------------------------
elif modo == "🔥 Sentimento de Mercado & Trending (B3)":
    st.markdown('<div class="main-header">🔥 Sentimento de Mercado & Trending na B3</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Radar de notícias em tempo real, ativos mais comentados e termômetro de Medo & Ganância.</div>', unsafe_allow_html=True)

    with st.spinner("Monitorando portais de notícias e menções de ativos da B3..."):
        sentiment_data = get_cached_sentiment()

    # Painel de Medo & Ganância (Fear & Greed)
    st.markdown("### 🧭 Termômetro de Medo & Ganância (B3 Sentiment Index)")
    
    fg_col1, fg_col2, fg_col3 = st.columns([1, 1, 1])
    with fg_col1:
        st.metric("Índice de Sentimento", f"{sentiment_data.fear_greed_score} / 100")
    with fg_col2:
        st.metric("Diagnóstico do Humor", sentiment_data.fear_greed_label)
    with fg_col3:
        st.metric("Balanço de Manchetes", f"🟢 {sentiment_data.positive_ratio}% Otimistas | 🔴 {sentiment_data.negative_ratio}% Alertas")

    st.progress(sentiment_data.fear_greed_score / 100)

    st.divider()

    # Ativos Mais Comentados
    st.markdown("### 🗣️ Ativos Mais Comentados do Momento na B3")
    st.caption("Ações e FIIs que estão liderando a cobertura e as atenções dos investidores hoje:")

    if sentiment_data.trending_assets:
        trend_cols = st.columns(min(len(sentiment_data.trending_assets), 4))
        for idx, asset in enumerate(sentiment_data.trending_assets[:4]):
            with trend_cols[idx]:
                badge_class = f"badge-{asset.sentiment_label.lower()}"
                st.markdown(f"#### {asset.ticker}")
                st.markdown(f"<span class='{badge_class}'>{asset.sentiment_label}</span>", unsafe_allow_html=True)
                st.write(f"**Menções:** {asset.mentions} notícias recentes")
                st.caption(f"\"{asset.sample_headline[:80]}...\"")
    else:
        st.info("Nenhum ativo com volume anormal de menções nas últimas horas.")

    st.divider()

    # Feed de Notícias em Tempo Real
    st.markdown("### 📰 Feed de Notícias Monitoradas com Classificação de Sentimento")
    for n in sentiment_data.news_feed:
        badge_class = f"badge-{n.sentiment_label.lower()}"
        tickers_str = " | ".join(n.mentioned_tickers) if n.mentioned_tickers else "B3 Geral"
        st.markdown(f"""
        <div class="news-card">
            <span class="{badge_class}">{n.sentiment_label}</span>
            <strong style="margin-left: 10px;">{tickers_str}</strong>
            <span style="float: right; color: #888888; font-size: 0.85rem;">{n.source} • {n.published}</span>
            <div style="margin-top: 8px;">
                <a href="{n.link}" target="_blank" style="text-decoration: none; color: #E0E0E0; font-size: 1.02rem; font-weight: 500;">
                    {n.title} ↗
                </a>
            </div>
        </div>
        """, unsafe_allow_html=True)
