"""مخططات الإدخال والإخراج لتحليل السير الذاتية."""
from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class ExtractUrlRequest(BaseModel):
    url: HttpUrl = Field(..., description="رابط صفحة تحتوي على السيرة الذاتية")


class ExtractedText(BaseModel):
    text: str


class CVAnalysisRequest(BaseModel):
    cv_text: str = Field(..., min_length=20, description="نص السيرة الذاتية")
    job_title: str = Field(..., description="المسمى الوظيفي المطلوب")
    domain: str | None = Field(None, description="المجال؛ افتراضياً المجال المفعّل")


class CriterionScore(BaseModel):
    key: str
    label_ar: str
    weight: int
    score: float = Field(..., ge=0, le=100, description="درجة المعيار من 100")
    justification_ar: str = Field(..., description="تبرير الدرجة")


class CVAnalysisResult(BaseModel):
    job_title: str
    domain: str
    overall_score: float = Field(..., ge=0, le=100, description="الدرجة الموزونة الكلية")
    recommendation_ar: str = Field(..., description="توصية للـ HR — لا قرار نهائي")
    scores: list[CriterionScore]
    strengths_ar: list[str]
    gaps_ar: list[str]
    disclaimer_ar: str = Field(
        default="هذا التقييم مساعد فقط. القرار النهائي يعود لفريق الموارد البشرية.",
    )


class ApplicationSubmitResponse(BaseModel):
    id: str
    message_ar: str = "تم استلام طلبك بنجاح. سيقوم فريق التوظيف بمراجعته والتواصل معك عند وجود تحديث."


class InterviewQuestion(BaseModel):
    id: str
    text: str
    source: str = Field(..., description="ai أو hr")
    type: str = Field("open", description="open أو mcq")
    options: list[str] | None = None
    correct_answer: str | None = None


class ApplicationSummary(BaseModel):
    id: str
    submitted_at: str
    full_name: str
    email: str
    phone: str | None = None
    job_title: str
    domain: str | None = None
    overall_score: float | None = None
    recommendation_ar: str | None = None
    analysis_error: str | None = None
    status: str = "pending"
    interview_datetime: str | None = None
    note_ar: str | None = None


class VoiceTranscriptTurn(BaseModel):
    question_index: int
    question: str
    answer: str


class VoiceDimensionScore(BaseModel):
    key: str
    label_ar: str
    score: float = Field(..., ge=0, le=100)
    justification_ar: str


class VoiceInterviewResult(BaseModel):
    scores: list[VoiceDimensionScore]
    overall_summary_ar: str


class WrittenAnswerResult(BaseModel):
    question_id: str
    question_text: str
    type: str
    candidate_answer: str
    correct_answer: str | None = None
    is_correct: bool | None = None
    score: float | None = None
    justification_ar: str | None = None


class WrittenTestResult(BaseModel):
    answers: list[WrittenAnswerResult]
    overall_score: float


class FinalRecommendation(BaseModel):
    recommend: bool
    reason_ar: str
    strengths_ar: list[str]
    weaknesses_ar: list[str]


class ApplicationDetail(ApplicationSummary):
    cv_text: str
    result: CVAnalysisResult | None = None
    questions: list[InterviewQuestion] = []
    voice_transcript: list[VoiceTranscriptTurn] = []
    voice_interview_result: VoiceInterviewResult | None = None
    written_test_result: WrittenTestResult | None = None
    final_recommendation: FinalRecommendation | None = None
    hiring_decision: str | None = None
    hiring_feedback_ar: str | None = None


class InterviewApproveRequest(BaseModel):
    interview_datetime: str = Field(..., description="موعد المقابلة بصيغة ISO 8601")
    note_ar: str | None = Field(None, description="ملاحظة للمرشح: مكان/رابط المقابلة مثلاً")


class InterviewRejectRequest(BaseModel):
    note_ar: str | None = None


class ApplicationStatusResponse(BaseModel):
    full_name: str
    job_title: str
    status: str = "pending"
    interview_datetime: str | None = None
    note_ar: str | None = None
    hiring_decision: str | None = None
    hiring_feedback_ar: str | None = None


class AddQuestionRequest(BaseModel):
    text: str = Field(..., min_length=3)
    options: list[str] | None = None
    correct_answer: str | None = None


class EditQuestionRequest(BaseModel):
    text: str = Field(..., min_length=3)
    options: list[str] | None = None
    correct_answer: str | None = None


class QuestionsResponse(BaseModel):
    questions: list[InterviewQuestion]


class VoiceInterviewQuestionsResponse(BaseModel):
    full_name: str
    job_title: str
    questions: list[str]


class VoiceTurnRequest(BaseModel):
    email: str
    question_index: int
    question_text: str
    answer_text: str = Field(..., min_length=1)


class VoiceEvaluateRequest(BaseModel):
    email: str


class WrittenAnswerItem(BaseModel):
    question_id: str
    answer_text: str = Field(..., min_length=1)


class WrittenTestSubmitRequest(BaseModel):
    answers: list[WrittenAnswerItem]


class HiringDecisionRequest(BaseModel):
    decision: str = Field(..., description="accepted أو rejected")
    feedback_ar: str | None = Field(
        None, description="ملاحظات ترسل للمرشح؛ افتراضياً تُبنى من التوصية النهائية"
    )
