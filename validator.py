import re
from typing import Dict, Any, List, Tuple
from models import StockData, ValidationResult, AnalysisVerdict

class AgentValidator:
    """Validador rigoroso de dados e de alucinações para o agente de ações da B3."""
    
    def __init__(self, stock_data: StockData):
        self.data = stock_data
        self.funds = stock_data.fundamentals
        self.tech = stock_data.technical
        
    def validate_pre_analysis(self) -> ValidationResult:
        """Validação dos dados brutos recebidos das APIs antes de alimentar o agente."""
        passed = []
        warnings = []
        errors = []
        
        # 1. Checagem de Preço e Cotação
        if self.funds.current_price > 0:
            passed.append(f"Preço atual válido: R$ {self.funds.current_price}")
        else:
            errors.append("Preço atual não encontrado ou zerado.")
            
        # 2. Checagem de Liquidez na B3
        min_volume = 1_000_000.0  # R$ 1 milhão diário
        if self.tech.avg_volume_30d:
            if self.tech.avg_volume_30d < min_volume:
                warnings.append(
                    f"Alerta de Liquidez B3: Volume médio diário (R$ {self.tech.avg_volume_30d:,.2f}) "
                    f"é inferior a R$ 1M. Risco de iliquidez elevado."
                )
            else:
                passed.append(f"Liquidez B3 adequada: R$ {self.tech.avg_volume_30d:,.2f}/dia")
        else:
            warnings.append("Volume financeiro médio não disponível para verificação de liquidez.")

        # 3. Consistência de Proventos e Lucro
        if self.funds.dividend_yield is not None:
            if self.funds.dividend_yield > 40.0:
                warnings.append(f"Dividend Yield anômalo ({self.funds.dividend_yield}%). Verificar se houve evento extraordinário.")
            else:
                passed.append("Dividend yield dentro de intervalo plausível.")
                
        # 4. Checagem de Alavancagem
        if self.funds.debt_to_ebitda is not None:
            if self.funds.debt_to_ebitda > 3.5:
                warnings.append(f"Alavancagem elevada: Dívida Líq./EBITDA em {self.funds.debt_to_ebitda}x. Sensível à Selic.")
            passed.append("Métrica de endividamento processada.")
            
        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            passed_checks=passed,
            warnings=warnings,
            errors=errors,
            hallucination_detected=False
        )

    def validate_post_analysis(
        self,
        verdict: AnalysisVerdict,
        valuation_summary: str,
        health_summary: str,
        key_risks: List[str]
    ) -> ValidationResult:
        """
        Fact-Checking pós-análise:
        1. Verifica se números citados nos resumos correspondem à verdade (Ground Truth).
        2. Verifica coerência entre as métricas e o veredito (ex: Dívida alta sem risco citado).
        """
        passed = []
        warnings = []
        errors = []
        hallucination_detected = False
        
        full_text = f"{valuation_summary} {health_summary}"
        
        # Fact-Check: P/L citado no texto
        pl_matches = re.findall(r"(?:P/L|Preço/Lucro|[Pp]reço/[Ll]ucro(?:\s*\([A-Za-z/]+\))?)(?:\s*(?:de|[:=]))?\s*([0-9]+[.,]?[0-9]*)", full_text)
        if pl_matches and self.funds.pe_ratio is not None:
            cited_val = float(pl_matches[0].replace(",", "."))
            real_val = float(self.funds.pe_ratio)
            # Permite tolerância de até 10% por arredondamento
            if abs(cited_val - real_val) / max(real_val, 0.01) > 0.10:
                errors.append(f"Alucinação Numérica: P/L citado ({cited_val}) diverge do dado real ({real_val}).")
                hallucination_detected = True
            else:
                passed.append(f"Fact-Check P/L: Valor citado no texto ({cited_val}) condiz com a base.")

        # Fact-Check: P/VP citado no texto
        pvp_matches = re.findall(r"(?:P/VP|P/VPA|Preço/Valor Patrimonial)(?:\s*(?:de|[:=]))?\s*([0-9]+[.,]?[0-9]*)", full_text, re.IGNORECASE)
        if pvp_matches and self.funds.pb_ratio is not None:
            cited_pvp = float(pvp_matches[0].replace(",", "."))
            real_pvp = float(self.funds.pb_ratio)
            if abs(cited_pvp - real_pvp) / max(real_pvp, 0.01) > 0.10:
                errors.append(f"Alucinação Numérica: P/VP citado ({cited_pvp}) diverge do dado real ({real_pvp}).")
                hallucination_detected = True
            else:
                passed.append(f"Fact-Check P/VP: Valor citado no texto ({cited_pvp}) condiz com a base.")
                
        # Fact-Check: Dividend Yield citado
        dy_matches = re.findall(r"(?:Dividend Yield|DY)(?: de|\s*[:=]\s*)?[\s]*([0-9]+[.,]?[0-9]*)%", full_text, re.IGNORECASE)
        if dy_matches and self.funds.dividend_yield is not None:
            cited_dy = float(dy_matches[0].replace(",", "."))
            real_dy = float(self.funds.dividend_yield)
            if abs(cited_dy - real_dy) > 1.5:  # tolerância de 1.5 pontos percentuais
                errors.append(f"Alucinação Numérica: DY citado ({cited_dy}%) diverge do dado real ({real_dy}%).")
                hallucination_detected = True
            else:
                passed.append("Fact-Check Dividend Yield: Condiz com o dado real.")

        # Checagem de Coerência com Riscos
        if self.funds.debt_to_ebitda and self.funds.debt_to_ebitda > 3.0:
            debt_mentioned = any("dívida" in r.lower() or "alavancagem" in r.lower() for r in key_risks)
            if not debt_mentioned:
                warnings.append(
                    f"Inconsistência de Tese: Empresa com Dívida/EBITDA de {self.funds.debt_to_ebitda}x, "
                    f"mas nenhum risco de alavancagem/endividamento foi listado."
                )
            else:
                passed.append("Coerência: Risco de dívida adequadamente refletido na tese.")

        if self.funds.roe and self.funds.roe < 0:
            if verdict == AnalysisVerdict.COMPRA:
                warnings.append("Alerta de Tese: Recomendação de COMPRA para empresa com ROE negativo (prejuízo).")
                
        is_valid = len(errors) == 0 and not hallucination_detected
        return ValidationResult(
            is_valid=is_valid,
            passed_checks=passed,
            warnings=warnings,
            errors=errors,
            hallucination_detected=hallucination_detected
        )
