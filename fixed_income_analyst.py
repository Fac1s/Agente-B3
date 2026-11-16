from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class MacroEconomicContext:
    selic_meta: float
    ipca_12m: float
    ipca_focus_proj: float
    di_1y: float
    di_5y: float
    risco_fiscal_status: str  # "Moderado", "Elevado", "Crítico"
    ciclo_monetario: str      # "Alta de Juros", "Corte de Juros", "Estabilidade"

@dataclass
class PublicBondAnalysis:
    tipo: str               # "Tesouro Selic", "Tesouro IPCA+", "Tesouro Prefixado"
    nome_titulo: str        # Ex: "Tesouro IPCA+ 2035"
    taxa_indicativa: str    # Ex: "IPCA + 6,75% a.a." ou "13,20% a.a."
    prazo_anos: int
    indicado_para: str
    marcação_a_mercado: str # "Baixo", "Moderado", "Muito Alto"
    veredito: str           # "FORTE COMPRA", "COMPRA", "NEUTRO / MANTER", "EVITAR"
    score_atratividade: int # 0 a 100
    tese_macro: str
    principais_vantagens: List[str]
    principais_riscos: List[str]

class FixedIncomeAnalyst:
    """Motor analítico de Renda Fixa Pública (Tesouro Direto) e Macroeconomia Brasileira."""

    def __init__(self, macro: Optional[MacroEconomicContext] = None):
        # Cenário macroeconômico atual do Brasil
        self.macro = macro or MacroEconomicContext(
            selic_meta=12.25,
            ipca_12m=4.60,
            ipca_focus_proj=4.10,
            di_1y=13.15,
            di_5y=13.40,
            risco_fiscal_status="Elevado",
            ciclo_monetario="Alta ou Manutenção em Dois Dígitos"
        )

    def analyze_tesouro_selic(self) -> PublicBondAnalysis:
        # Tesouro Selic (LFT)
        selic = self.macro.selic_meta
        score = 90 if selic >= 10.0 else 70
        
        return PublicBondAnalysis(
            tipo="Tesouro Selic (Pós-Fixado)",
            nome_titulo="Tesouro Selic 2029 / 2031",
            taxa_indicativa=f"Selic + 0,08% a.a. (~{selic:.2f}% a.a.)",
            prazo_anos=4,
            indicado_para="Reserva de emergência, liquidez diária e preservação de capital sem volatilidade.",
            marcação_a_mercado="Baixo (Volatilidade quase nula na venda antecipada)",
            veredito="FORTE COMPRA" if selic >= 11.0 else "COMPRA",
            score_atratividade=score,
            tese_macro=(
                f"Com a taxa Selic em patamar elevado ({selic:.2f}%), o carrego do Tesouro Selic "
                f"oferece um dos melhores retornos ajustados ao risco do mundo (~1% ao mês líquido de inflação), "
                f"sem expor o investidor ao risco de marcação a mercado negativo caso a curva de juros longa abra."
            ),
            principais_vantagens=[
                "Liquidez D+1 garantida pelo Tesouro Nacional.",
                "Rendimento diário positivo, sem sobressaltos.",
                "Excelente proteção caso o Banco Central decida elevar os juros para conter a inflação."
            ],
            principais_riscos=[
                "Custo de oportunidade caso ocorra um ciclo acelerado de cortes de juros futuros.",
                "Alíquota regressiva de IR para resgates antes de 2 anos."
            ]
        )

    def analyze_tesouro_ipca(self) -> PublicBondAnalysis:
        # Tesouro IPCA+ (NTN-B Principal)
        taxa_real_estimada = 6.70  # IPCA + 6,70%
        score = 95 if taxa_real_estimada >= 6.5 else (80 if taxa_real_estimada >= 5.8 else 60)

        return PublicBondAnalysis(
            tipo="Tesouro IPCA+ (Híbrido com Cupom Real)",
            nome_titulo="Tesouro IPCA+ 2029 / 2035 / 2045",
            taxa_indicativa=f"IPCA + {taxa_real_estimada:.2f}% a.a.",
            prazo_anos=10,
            indicado_para="Aposentadoria, ganho real de capital a longo prazo e proteção definitiva contra a inflação.",
            marcação_a_mercado="Muito Alto (Títulos longos sofrem forte oscilação de preço no curto prazo)",
            veredito="FORTE COMPRA (Assimetria Histórica)",
            score_atratividade=score,
            tese_macro=(
                f"Taxas reais no patamar de IPCA + {taxa_real_estimada:.2f}% situam-se no percentil histórico mais alto "
                f"da história do Tesouro Direto. Essa taxa garante que o patrimônio dobre em poder de compra em cerca de "
                f"10 a 11 anos, independentemente do que acontecer com a inflação no Brasil. Além disso, se o estresse fiscal "
                f"arrefecer, o investidor pode obter lucros expressivos via marcação a mercado."
            ),
            principais_vantagens=[
                "Garantia de aumento real do poder de compra acima da inflação oficial.",
                "Potencial de lucro substancial na marcação a mercado caso os juros futuros caiam.",
                "Indexador soberano contra choques cambiais e de combustíveis/alimentos."
            ],
            principais_riscos=[
                "Marcação a mercado severa no curto prazo se o risco fiscal continuar se deteriorando.",
                "Exige disciplina para não resgatar antecipadamente em momentos de pânico na curva de juros."
            ]
        )

    def analyze_tesouro_prefixado(self) -> PublicBondAnalysis:
        # Tesouro Prefixado (LTN)
        taxa_pre = 13.25
        score = 65 if self.macro.ciclo_monetario == "Alta ou Manutenção em Dois Dígitos" else 85

        return PublicBondAnalysis(
            tipo="Tesouro Prefixado",
            nome_titulo="Tesouro Prefixado 2027 / 2031",
            taxa_indicativa=f"{taxa_pre:.2f}% a.a. fixa",
            prazo_anos=3,
            indicado_para="Investidores com convicção de queda rápida da Selic e da inflação no médio prazo.",
            marcação_a_mercado="Moderado a Alto",
            veredito="NEUTRO / MANTER" if "Alta" in self.macro.ciclo_monetario else "COMPRA",
            score_atratividade=score,
            tese_macro=(
                f"Embora uma taxa fixa de {taxa_pre:.2f}% a.a. pareça tentadora, títulos prefixados exigem cautela sob "
                f"risco fiscal elevado. Se o IPCA voltar a subir para 5-6% e a Selic permanecer alta por mais tempo, "
                f"o retorno real líquido encolhe consideravelmente. Só é recomendado com horizonte até 2027 ou para travar taxa."
            ),
            principais_vantagens=[
                "Previsibilidade total do valor a ser recebido no vencimento.",
                "Excelente retorno caso o Banco Central consiga derrubar os juros mais rápido que o precificado."
            ],
            principais_riscos=[
                "Vulnerabilidade absoluta a repiques de inflação (risco de juro real negativo).",
                "Perda na venda antecipada se a curva longa de juros continuar abrindo."
            ]
        )

    def simulate_investment(self, aporte: float, anos: int) -> Dict[str, Any]:
        """Simula a rentabilidade comparativa no prazo selecionado."""
        selic_efetiva = self.macro.selic_meta / 100
        ipca_proj = self.macro.ipca_focus_proj / 100
        taxa_real_ipca = 0.067
        taxa_pre = 0.1325
        poupanca_proj = 0.0617 # Poupança sob Selic > 8.5% rende 0.5% a.m. + TR (~6.17% a.a.)

        # Alíquota de IR (15% para prazos > 2 anos)
        ir_rate = 0.15 if anos >= 2 else (0.175 if anos >= 1 else 0.225)

        # 1. Tesouro Selic
        bruto_selic = aporte * ((1 + selic_efetiva) ** anos)
        lucro_selic = bruto_selic - aporte
        liq_selic = aporte + (lucro_selic * (1 - ir_rate))

        # 2. Tesouro IPCA+
        taxa_total_ipca = ((1 + ipca_proj) * (1 + taxa_real_ipca)) - 1
        bruto_ipca = aporte * ((1 + taxa_total_ipca) ** anos)
        lucro_ipca = bruto_ipca - aporte
        liq_ipca = aporte + (lucro_ipca * (1 - ir_rate))

        # 3. Tesouro Prefixado
        bruto_pre = aporte * ((1 + taxa_pre) ** anos)
        lucro_pre = bruto_pre - aporte
        liq_pre = aporte + (lucro_pre * (1 - ir_rate))

        # 4. Poupança (Isenta de IR)
        liq_poupanca = aporte * ((1 + poupanca_proj) ** anos)

        return {
            "aporte": aporte,
            "anos": anos,
            "tesouro_selic": round(liq_selic, 2),
            "tesouro_ipca": round(liq_ipca, 2),
            "tesouro_prefixado": round(liq_pre, 2),
            "poupanca": round(liq_poupanca, 2),
            "ganho_extra_vs_poupanca": round(max(liq_ipca, liq_selic) - liq_poupanca, 2)
        }
