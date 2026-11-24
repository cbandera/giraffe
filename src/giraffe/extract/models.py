from dataclasses import dataclass, field

E_INVOICE, TEXT, MANUAL = "e-invoice", "text", "manual"


@dataclass
class PaymentData:
    payee: str = ""
    iban: str = ""
    bic: str = ""
    amount: str = ""        # normalized "1234.56" or ""
    currency: str = "EUR"
    remittance: str = ""
    sources: dict[str, str] = field(default_factory=dict)
    iban_candidates: list[str] = field(default_factory=list)
    amount_candidates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def set(self, name: str, value: str, source: str) -> None:
        if value:
            setattr(self, name, value)
            self.sources[name] = source

    def source(self, name: str) -> str:
        return self.sources.get(name, "") if getattr(self, name) else ""
