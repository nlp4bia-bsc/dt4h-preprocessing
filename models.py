from pydantic import BaseModel, model_validator, ConfigDict


class RecordInput(BaseModel):
    model_config = ConfigDict(extra='allow')

    patient_id: str
    text_path: str
    admission_id: str | None = None
    contact_id: str | None = None

    @model_validator(mode='after')
    def require_contact_or_admission(self):
        if self.admission_id is None and self.contact_id is None:
            raise ValueError('admission_id or contact_id required')
        return self
