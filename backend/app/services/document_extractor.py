"""استخراج نص السيرة الذاتية من ملف مرفق أو رابط موقع."""
from __future__ import annotations

import ipaddress
import socket
from io import BytesIO
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_TEXT_LENGTH = 20_000
REQUEST_TIMEOUT = 10.0


class ExtractionError(Exception):
    pass


def extract_text_from_file(filename: str, content: bytes) -> str:
    if len(content) > MAX_FILE_SIZE:
        raise ExtractionError("حجم الملف أكبر من الحد المسموح (5MB).")

    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if suffix == "pdf":
        text = _extract_pdf(content)
    elif suffix == "docx":
        text = _extract_docx(content)
    elif suffix in ("txt", "md"):
        text = content.decode("utf-8", errors="ignore")
    else:
        raise ExtractionError(
            "صيغة الملف غير مدعومة. الصيغ المدعومة: PDF, DOCX, TXT."
        )

    text = text.strip()
    if not text:
        raise ExtractionError("لم يتم العثور على نص قابل للقراءة داخل الملف.")
    return text[:MAX_TEXT_LENGTH]


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        raise ExtractionError(f"تعذّر قراءة ملف PDF: {e}")


def _extract_docx(content: bytes) -> str:
    try:
        doc = Document(BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        raise ExtractionError(f"تعذّر قراءة ملف Word: {e}")


def _assert_public_host(hostname: str) -> None:
    """يمنع الوصول لعناوين الشبكة الداخلية/المحلية (حماية من SSRF)."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ExtractionError("تعذّر الوصول للموقع: تعذّر تحليل اسم النطاق.")

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ExtractionError("لا يُسمح بجلب روابط تشير لشبكات داخلية/محلية.")


def extract_text_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ExtractionError("الرابط غير صالح. يجب أن يبدأ بـ http:// أو https://")

    _assert_public_host(parsed.hostname)

    try:
        response = httpx.get(
            url,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=False,
            headers={"User-Agent": "HR-Agent/1.0"},
        )
    except httpx.HTTPError as e:
        raise ExtractionError(f"تعذّر الوصول للرابط: {e}")

    if response.is_redirect:
        raise ExtractionError(
            "الرابط يقوم بإعادة توجيه. الرجاء استخدام الرابط النهائي مباشرة."
        )
    if response.status_code >= 400:
        raise ExtractionError(f"الموقع أعاد خطأ: {response.status_code}")

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        raise ExtractionError("محتوى الرابط ليس صفحة نصية/HTML مدعومة.")

    if "text/plain" in content_type:
        text = response.text
    else:
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines).strip()

    if not text:
        raise ExtractionError("لم يتم العثور على نص قابل للقراءة في الصفحة.")
    return text[:MAX_TEXT_LENGTH]
