from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AnalysisVerdict(str, Enum):
    COMPRA = "COMPRA"
    MANTER = "MANTER"
    VENDA = "VENDA"

class StockFundamentals(BaseModel):
    ticker: str
    company_name: str
    sector: str
    industry: str
    current_price: float
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = Field(None, description="Preço / Lucro (P/L)")
    pb_ratio: Optional[float] = Field(None, description="Preço / Valor Patrimonial (P/VP)")
    ev_ebitda: Optional[float] = Field(None, description="EV / EBITDA")
    dividend_yield: Optional[float] = Field(None, description="Dividend Yield (%)")
    payout_ratio: Optional[float] = Field(None, description="Payout Ratio (%)")
    roe: Optional[float] = Field(None, description="Retorno sobre Patrimônio Líquido (%)")
    net_margin: Optional[float] = Field(None, description="Margem Líquida (%)")
    ebitda_margin: Optional[float] = Field(None, description="Margem EBITDA (%)")
    debt_to_ebitda: Optional[float] = Field(None, description="Dívida Líquida / EBITDA")
    free_cashflow: Optional[float] = None

class StockTechnical(BaseModel):
    current_price: float
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi_14: Optional[float] = Field(None, description="IFR de 14 períodos")
    avg_volume_30d: Optional[float] = Field(None, description="Volume financeiro médio diário")

class StockData(BaseModel):
    ticker: str
    fundamentals: StockFundamentals
    technical: StockTechnical
    timestamp: str

class ValidationResult(BaseModel):
    is_valid: bool
    passed_checks: List[str]
    warnings: List[str]
    errors: List[str]
    hallucination_detected: bool = False

class AnalysisReport(BaseModel):
    ticker: str
    company_name: str
    sector: str
    timestamp: str
    verdict: AnalysisVerdict
    fundamental_score: int = Field(..., ge=0, le=100, description="Score de 0 a 100")
    valuation_summary: str
    financial_health_summary: str
    macro_sensitivity: str
    key_catalysts: List[str]
    key_risks: List[str]
    ground_truth_data: Dict[str, Any]
    validation: ValidationResult
