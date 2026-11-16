import os
import json
import unicodedata
from datetime import datetime
from typing import List, Dict, Any, Tuple
from models import StockData, AnalysisReport, AnalysisVerdict, ValidationResult
from validator import AgentValidator

def strip_accents(s: str) -> str:
    """Remove acentos e converte para minúsculas para comparações seguras."""
    if not s:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()

class B3StockAnalyst:
    """Motor de análise e recomendação para ações listadas na B3."""
    
    def __init__(self, stock_data: StockData):
        self.data = stock_data
        self.funds = stock_data.fundamentals
        self.tech = stock_data.technical
        self.validator = AgentValidator(stock_data)

    def calculate_fundamental_score(self) -> Tuple[int, Dict[str, int]]:
        """
        Calcula um Score Fundamentalista ponderado (0 a 100) calibrado para a B3:
        - Valuation: 30 pts
        - Rentabilidade / Eficiência: 30 pts
        - Saúde Financeira / Endividamento: 20 pts
        - Retorno em Dividendos (DY): 20 pts
        """
        scores = {}
        
        # 1. Valuation (Max 30 pts)
        val_score = 0
        if self.funds.pe_ratio is not None:
            if 0 < self.funds.pe_ratio <= 8:
                val_score += 15
            elif 8 < self.funds.pe_ratio <= 14:
                val_score += 10
            elif 14 < self.funds.pe_ratio <= 20:
                val_score += 5
        if self.funds.pb_ratio is not None:
            if 0 < self.funds.pb_ratio <= 1.2:
                val_score += 10
            elif 1.2 < self.funds.pb_ratio <= 2.0:
                val_score += 6
        if self.funds.ev_ebitda is not None:
            if 0 < self.funds.ev_ebitda <= 6:
                val_score += 5
            elif 6 < self.funds.ev_ebitda <= 9:
                val_score += 3
        scores["valuation"] = min(val_score, 30)

        # 2. Rentabilidade e Margens (Max 30 pts)
        rent_score = 0
        if self.funds.roe is not None:
            if self.funds.roe >= 20.0:
                rent_score += 18
            elif self.funds.roe >= 14.0:
                rent_score += 13
            elif self.funds.roe >= 8.0:
                rent_score += 7
        if self.funds.net_margin is not None:
            if self.funds.net_margin >= 15.0:
                rent_score += 12
            elif self.funds.net_margin >= 8.0:
                rent_score += 8
            elif self.funds.net_margin >= 3.0:
                rent_score += 4
        scores["rentabilidade"] = min(rent_score, 30)

        # 3. Endividamento e Solvência (Max 20 pts)
        is_financial = any(w in strip_accents(self.funds.sector) for w in ["financ", "banc", "bank", "segur", "insur"])
        if is_financial:
            # Em bancos e seguradoras, Dívida/EBITDA não se aplica. Pontuação calibrada pela margem/ROE.
            debt_score = 18 if (self.funds.roe and self.funds.roe >= 15) else 14
        elif self.funds.debt_to_ebitda is not None:
            if self.funds.debt_to_ebitda <= 1.5:
                debt_score = 20
            elif self.funds.debt_to_ebitda <= 2.5:
                debt_score = 15
            elif self.funds.debt_to_ebitda <= 3.5:
                debt_score = 8
            else:
                debt_score = 2
        else:
            debt_score = 10
        scores["solvencia"] = debt_score

        # 4. Proventos / Projeção de Dividendos (Max 20 pts)
        div_score = 0
        if self.funds.dividend_yield is not None:
            if self.funds.dividend_yield >= 8.0:
                div_score = 20
            elif self.funds.dividend_yield >= 6.0:
                div_score = 15
            elif self.funds.dividend_yield >= 4.0:
                div_score = 10
            elif self.funds.dividend_yield > 0:
                div_score = 5
        scores["proventos"] = div_score

        total_score = sum(scores.values())
        return total_score, scores

    def determine_verdict(self, score: int) -> AnalysisVerdict:
        if score >= 68:
            return AnalysisVerdict.COMPRA
        elif score >= 48:
            return AnalysisVerdict.MANTER
        else:
            return AnalysisVerdict.VENDA

    def generate_report(self) -> AnalysisReport:
        """Gera o relatório de análise estruturado e aplica a validação."""
        # 1. Pré-Validação dos Dados Brutos
        pre_val = self.validator.validate_pre_analysis()
        
        # 2. Cálculo do Score
        score, score_breakdown = self.calculate_fundamental_score()
        verdict = self.determine_verdict(score)
        
        # 3. Elaboração do Texto com Ground-Truth Explícito
        pe_str = f"{self.funds.pe_ratio:.2f}" if self.funds.pe_ratio is not None else "N/A"
        pb_str = f"{self.funds.pb_ratio:.2f}" if self.funds.pb_ratio is not None else "N/A"
        ev_str = f"{self.funds.ev_ebitda:.2f}" if self.funds.ev_ebitda is not None else "N/A"
        dy_str = f"{self.funds.dividend_yield:.2f}" if self.funds.dividend_yield is not None else "0.00"
        roe_str = f"{self.funds.roe:.2f}%" if self.funds.roe is not None else "N/A"
        margin_str = f"{self.funds.net_margin:.2f}%" if self.funds.net_margin is not None else "N/A"
        debt_str = f"{self.funds.debt_to_ebitda:.2f}x" if self.funds.debt_to_ebitda is not None else "N/A"
        
        valuation_summary = (
            f"A empresa negocia atualmente a um Preço/Lucro (P/L) de {pe_str} e P/VP de {pb_str}, "
            f"com EV/EBITDA de {ev_str}. O retorno via proventos apresenta um Dividend Yield de {dy_str}%. "
            f"Diante do score de valuation ({score_breakdown['valuation']}/30), os múltiplos indicam "
            f"{'desconto atrativo frente à média histórica' if score_breakdown['valuation'] >= 20 else 'preço justo ou sem margem de segurança evidente'}."
        )

        sector_clean = strip_accents(self.funds.sector)
        is_financial = any(w in sector_clean for w in ["financ", "banc", "bank", "segur", "insur"])
        
        if is_financial:
            health_summary = (
                f"A rentabilidade sobre o patrimônio líquido (ROE) situa-se em {roe_str}, com margem líquida de {margin_str}. "
                f"Para instituições financeiras, a métrica tradicional de Dívida Líquida/EBITDA não se aplica diretamente (o foco analítico é Basileia e PDD). "
                f"{'A rentabilidade é elevada e assegura capacidade sólida de crédito' if self.funds.roe and self.funds.roe >= 15 else 'A rentabilidade requer acompanhamento de inadimplência e provisões'}."
            )
        else:
            health_summary = (
                f"A rentabilidade sobre o patrimônio líquido (ROE) situa-se em {roe_str}, com margem líquida de {margin_str}. "
                f"Em termos de endividamento, a relação Dívida Líquida / EBITDA é de {debt_str}. "
                f"{'A estrutura de capital é conservadora e resiliente' if self.funds.debt_to_ebitda and self.funds.debt_to_ebitda < 2.5 else 'A dívida exige atenção contínua, especialmente em ciclos de política monetária restritiva'}."
            )

        # 4. Sensibilidade Macroeconômica (Brasil)
        if any(w in sector_clean for w in ["financ", "banc", "bank", "segur", "insur"]):
            macro = "Sensibilidade aos juros (Selic elevada beneficia margens financeiras e spreads bancários, mas eleva inadimplência e custo de funding)."
        elif any(w in sector_clean for w in ["utilidad", "eletric", "saneament", "transmissao", "power"]):
            macro = "Perfil defensivo. Receitas atreladas a contratos de longo prazo reajustados por inflação (IPCA/IGP-M) com alta previsibilidade de dividendos."
        elif any(w in sector_clean for w in ["energia", "energy", "petrol", "oil", "gas", "minerac", "basic materials", "siderurg", "agric", "papel"]):
            macro = "Forte correlação com commodities globais (petróleo/minério) e taxa de câmbio (USD/BRL). Menor dependência do PIB doméstico."
        elif any(w in sector_clean for w in ["varej", "retail", "consum", "construc", "imobil", "real estate"]):
            macro = "Alta sensibilidade cíclica ao ciclo doméstico: juros (Selic), inflação na renda disponível e nível de emprego."
        else:
            macro = "Sensível ao consumo doméstico brasileiro, taxa de juros local e custo de capital."

        # 5. Catalisadores e Riscos
        catalysts = []
        if self.funds.dividend_yield and self.funds.dividend_yield >= 6.0:
            catalysts.append(f"Geração de renda passiva robusta (Dividend Yield atual de {dy_str}%).")
        if self.funds.pe_ratio and self.funds.pe_ratio < 10:
            catalysts.append(f"Múltiplo de P/L descontado ({pe_str}), oferecendo potencial de reprecificação.")
        if self.funds.roe and self.funds.roe >= 15:
            catalysts.append(f"Alta capacidade de reinvestimento do capital (ROE de {roe_str}).")
        if self.tech.rsi_14 and self.tech.rsi_14 < 35:
            catalysts.append(f"Momento técnico: Ativo em região de sobrevenda (IFR 14 = {self.tech.rsi_14}).")
        if not catalysts:
            catalysts.append("Possível recuperação operacional e ganho de eficiência no médio prazo.")

        risks = []
        if self.funds.debt_to_ebitda and self.funds.debt_to_ebitda > 2.5:
            risks.append(f"Alavancagem financeira: Dívida Líq./EBITDA de {debt_str} encarece o serviço da dívida sob Selic alta.")
        if self.tech.avg_volume_30d and self.tech.avg_volume_30d < 3_000_000:
            risks.append("Liquidez B3: Volume médio diário negociado reduzido, aumentando risco de spread na execução.")
        risks.append("Risco macroeconômico brasileiro: Volatilidade fiscal, taxa Selic de dois dígitos e oscilação cambial.")
        if self.funds.roe and self.funds.roe < 8:
            risks.append(f"Rentabilidade comprimida: Retorno sobre capital (ROE {roe_str}) abaixo do custo de oportunidade da renda fixa.")

        # 6. Validação Pós-Análise (Fact-Checking contra alucinações numéricas)
        post_val = self.validator.validate_post_analysis(
            verdict=verdict,
            valuation_summary=valuation_summary,
            health_summary=health_summary,
            key_risks=risks
        )
        
        # Consolidação dos resultados de validação
        combined_validation = ValidationResult(
            is_valid=pre_val.is_valid and post_val.is_valid,
            passed_checks=pre_val.passed_checks + post_val.passed_checks,
            warnings=pre_val.warnings + post_val.warnings,
            errors=pre_val.errors + post_val.errors,
            hallucination_detected=post_val.hallucination_detected
        )

        return AnalysisReport(
            ticker=self.funds.ticker,
            company_name=self.funds.company_name,
            sector=self.funds.sector,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            verdict=verdict,
            fundamental_score=score,
            valuation_summary=valuation_summary,
            financial_health_summary=health_summary,
            macro_sensitivity=macro,
            key_catalysts=catalysts,
            key_risks=risks,
            ground_truth_data={
                "current_price": self.funds.current_price,
                "pe_ratio": self.funds.pe_ratio,
                "pb_ratio": self.funds.pb_ratio,
                "ev_ebitda": self.funds.ev_ebitda,
                "dividend_yield": self.funds.dividend_yield,
                "roe": self.funds.roe,
                "net_margin": self.funds.net_margin,
                "debt_to_ebitda": self.funds.debt_to_ebitda,
                "rsi_14": self.tech.rsi_14,
                "avg_daily_volume": self.tech.avg_volume_30d
            },
            validation=combined_validation
        )
