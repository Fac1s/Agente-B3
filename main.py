import argparse
import sys
import json
import os
from pathlib import Path
from models import StockData, StockFundamentals, StockTechnical, AnalysisReport
from data_fetcher import fetch_b3_stock
from analyst import B3StockAnalyst
from screener import B3MarketScreener, MarketScreeningReport

def get_mock_b3_data(ticker: str) -> StockData:
    """Dados de fallback para testes offline ou demonstração rápida."""
    ticker_clean = ticker.upper().replace(".SA", "")
    return StockData(
        ticker=ticker_clean,
        fundamentals=StockFundamentals(
            ticker=ticker_clean,
            company_name=f"{ticker_clean} Petróleo Brasileiro S.A. (Demo)" if "PETR" in ticker_clean else f"{ticker_clean} S.A. (Demo)",
            sector="Energy" if "PETR" in ticker_clean else "Financial Services",
            industry="Exploração e Refino",
            current_price=37.50,
            market_cap=485_000_000_000.0,
            pe_ratio=4.85,
            pb_ratio=1.10,
            ev_ebitda=3.20,
            dividend_yield=14.20,
            payout_ratio=45.0,
            roe=24.50,
            net_margin=22.30,
            ebitda_margin=41.00,
            debt_to_ebitda=1.15,
            free_cashflow=42_000_000_000.0
        ),
        technical=StockTechnical(
            current_price=37.50,
            high_52w=42.00,
            low_52w=31.20,
            sma_50=36.80,
            sma_200=35.10,
            rsi_14=46.5,
            avg_volume_30d=1_450_000_000.0
        ),
        timestamp="2026-11-16 14:00:00"
    )

def print_banner(title: str = "AGENTE ANALISTA DE AÇÕES DA B3 - RELATÓRIO OFICIAL"):
    print("=" * 75)
    print(f"        {title}        ")
    print("=" * 75)

def render_terminal(report: AnalysisReport):
    print_banner()
    print(f" Ativo: {report.ticker} | {report.company_name}")
    print(f" Setor: {report.sector}")
    print(f" Data da Análise: {report.timestamp}")
    print("-" * 75)
    
    # Veredito e Score
    verdict_colors = {
        "COMPRA": "[VEREDITO: COMPRA] \u2705",
        "MANTER": "[VEREDITO: MANTER] \u26A0\uFE0F",
        "VENDA":  "[VEREDITO: VENDA]  \u274C"
    }
    verdict_display = verdict_colors.get(report.verdict.value, report.verdict.value)
    print(f"\n{verdict_display}  |  Score Fundamentalista: {report.fundamental_score}/100")
    print("-" * 75)
    
    # Resumos
    print("\n\U0001F4CA AVALIAÇÃO DE VALUATION:")
    print(f"  {report.valuation_summary}")
    
    print("\n\U0001F3E5 SAÚDE FINANCEIRA & EFICIÊNCIA:")
    print(f"  {report.financial_health_summary}")
    
    print("\n\U0001F30E SENSIBILIDADE MACROECONÔMICA (BRASIL):")
    print(f"  {report.macro_sensitivity}")
    
    print("\n\U0001F680 PRINCIPAIS CATALISADORES:")
    for cat in report.key_catalysts:
        print(f"  \u2022 {cat}")
        
    print("\n\u26A0\uFE0F PRINCIPAIS RISCOS:")
    for r in report.key_risks:
        print(f"  \u2022 {r}")
        
    # Auditoria de Validação
    print("\n" + "=" * 75)
    print("                    AUDITORIA & VALIDAÇÃO DO AGENTE                  ")
    print("=" * 75)
    v = report.validation
    status_icon = "\u2705 APROVADO" if v.is_valid else "\u274C REPROVADO"
    print(f"Status da Validação: {status_icon}")
    print(f"Alucinações Numéricas Detectadas: {'SIM \u26A0\uFE0F' if v.hallucination_detected else 'NENHUMA \u2705'}")
    
    print("\nChecagens Concluídas com Sucesso:")
    for p in v.passed_checks:
        print(f"  [\u2713] {p}")
        
    if v.warnings:
        print("\nAlertas Emitidos:")
        for w in v.warnings:
            print(f"  [!] {w}")
            
    if v.errors:
        print("\nErros / Inconsistências:")
        for e in v.errors:
            print(f"  [\u2717] {e}")
    print("=" * 75)

def export_markdown(report: AnalysisReport, output_path: str):
    md_content = f"""# Relatório de Análise B3: {report.ticker} - {report.company_name}

**Data da Análise:** {report.timestamp}  
**Setor:** {report.sector}  
**Veredito:** **`{report.verdict.value}`**  
**Score Fundamentalista:** **{report.fundamental_score} / 100**  

---

## 1. Avaliação de Valuation
{report.valuation_summary}

## 2. Saúde Financeira & Eficiência
{report.financial_health_summary}

## 3. Sensibilidade Macroeconômica (Cenário Brasil)
{report.macro_sensitivity}

---

## 4. Catalisadores de Alta
{chr(10).join([f"- {c}" for c in report.key_catalysts])}

## 5. Fatores de Risco
{chr(10).join([f"- {r}" for r in report.key_risks])}

---

## 6. Auditoria de Validação do Agente (Ground-Truth Check)

| Métrica Auditada | Valor Real na Base |
| :--- | :--- |
| Preço Atual | R$ {report.ground_truth_data.get('current_price', 0):.2f} |
| P/L | {report.ground_truth_data.get('pe_ratio', 'N/A')} |
| P/VP | {report.ground_truth_data.get('pb_ratio', 'N/A')} |
| EV/EBITDA | {report.ground_truth_data.get('ev_ebitda', 'N/A')} |
| Dividend Yield | {report.ground_truth_data.get('dividend_yield', 0):.2f}% |
| ROE | {report.ground_truth_data.get('roe', 'N/A')}% |
| Dívida Líq. / EBITDA | {report.ground_truth_data.get('debt_to_ebitda', 'N/A')}x |
| IFR 14 (Técnico) | {report.ground_truth_data.get('rsi_14', 'N/A')} |

### Status do Fact-Checking
* **Resultado:** {'APROVADO' if report.validation.is_valid else 'COM RESTRIÇÕES'}
* **Alucinação Numérica Detectada:** {'SIM' if report.validation.hallucination_detected else 'NÃO'}
* **Checagens Bem-Sucedidas:** {len(report.validation.passed_checks)}
* **Alertas:** {len(report.validation.warnings)}
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n[OK] Relatório Markdown salvo em: {output_path}")

def run_screener_mode(universe: str = "ibov", top_n: int = 5):
    """Executa a varredura geral na B3 para identificar oportunidades com grande assimetria."""
    print_banner(f"VARREDURA GERAL B3 [{universe.upper()}]: DEEP VALUE & OPORTUNIDADES")
    screener = B3MarketScreener(universe=universe)
    report: MarketScreeningReport = screener.scan_market(top_n=top_n)

    print("\n" + "=" * 75)
    print("        TOP OPORTUNIDADES DE MAIOR ASSIMETRIA E POTENCIAL NA B3       ")
    print("=" * 75)
    
    for i, opp in enumerate(report.top_opportunities, 1):
        pl_str = f"{opp.pe_ratio:.1f}x" if opp.pe_ratio else "N/A"
        pvp_str = f"{opp.pb_ratio:.2f}x" if opp.pb_ratio else "N/A"
        roe_str = f"{opp.roe:.1f}%" if opp.roe else "N/A"
        dy_str = f"{opp.dividend_yield:.1f}%" if opp.dividend_yield else "0.0%"
        rsi_str = f"{opp.rsi_14:.1f}" if opp.rsi_14 else "N/A"
        
        print(f"\n#{i} \u2705 {opp.ticker} - {opp.company_name} ({opp.sector})")
        print(f"   Preço: R$ {opp.current_price:.2f} | Upside Score: {opp.total_upside_score}/100")
        print(f"   Múltiplos: P/L: {pl_str} | P/VP: {pvp_str} | ROE: {roe_str} | DY: {dy_str} | IFR 14: {rsi_str}")
        print(f"   Sub-Scores: Desconto: {opp.deep_value_score}/100 | Qualidade: {opp.quality_score}/100 | Catalisador: {opp.catalyst_score}/100")
        print(f"   Tese: {opp.primary_thesis.capitalize()}.")

    print("\n" + "=" * 75)

    # Salva relatórios
    output_dir = Path(__file__).parent / "reports"
    output_dir.mkdir(exist_ok=True)
    
    md_path = output_dir / "ranking_oportunidades_b3.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report.summary_markdown)
    print(f"\n[OK] Ranking completo em Markdown salvo em: {md_path}")

    json_path = output_dir / "ranking_oportunidades_b3.json"
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"[OK] Dados da varredura salvos em JSON: {json_path}")

    # Se houver oportunidades, gera o relatório aprofundado para o ativo #1
    if report.top_opportunities:
        best_ticker = report.top_opportunities[0].ticker
        print(f"\n>>> Gerando Análise Aprofundada e Fact-Checking do Ativo #1 ({best_ticker})...\n")
        run_single_ticker_analysis(best_ticker)

def run_single_ticker_analysis(ticker: str, demo: bool = False):
    print(f"Iniciando análise aprofundada para {ticker}...")
    stock_data = None
    if not demo:
        try:
            print("Tentando coletar dados em tempo real...")
            stock_data = fetch_b3_stock(ticker)
        except Exception as e:
            print(f"[Aviso] Falha ao conectar em tempo real ({e}). Alternando para modo demo.")
            stock_data = get_mock_b3_data(ticker)
    else:
        stock_data = get_mock_b3_data(ticker)

    analyst = B3StockAnalyst(stock_data)
    report = analyst.generate_report()

    # Exibe no terminal
    render_terminal(report)

    output_dir = Path(__file__).parent / "reports"
    output_dir.mkdir(exist_ok=True)
    
    json_path = output_dir / f"analise_{ticker}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"[OK] Dados JSON salvos em: {json_path}")

    md_path = output_dir / f"relatorio_{ticker}.md"
    export_markdown(report, str(md_path))

def main():
    parser = argparse.ArgumentParser(description="Agente Analista e Rastreador de Ações B3")
    parser.add_argument("--ticker", type=str, default=None, help="Código de uma ação específica na B3 (ex: PETR4, VALE3)")
    parser.add_argument("--scan", action="store_true", help="Executar varredura ampla no mercado B3 em busca de oportunidades descontadas")
    parser.add_argument("--universe", type=str, default="ibov", choices=["ibov", "smallcaps", "dividendos", "all"], help="Universo a varrer: ibov (80+ ações), smallcaps, dividendos, all (110+ ações)")
    parser.add_argument("--top", type=int, default=5, help="Número de top oportunidades a exibir (padrão: 5)")
    parser.add_argument("--demo", action="store_true", help="Executar em modo demonstração com dados simulados")
    args = parser.parse_args()

    if args.ticker:
        run_single_ticker_analysis(args.ticker.upper().strip(), demo=args.demo)
    else:
        # Se nenhum ticker for especificado, executa a varredura ampla do mercado!
        run_screener_mode(universe=args.universe, top_n=args.top)

if __name__ == "__main__":
    main()
