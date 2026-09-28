from io import BytesIO
import zipfile
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from app.knowledge import extract_sections, extract_text, chunk_text, validate_answer, focus_sources
from app.schemas import GroundedAnswer


def pdf_bytes(text=None):
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    if text:
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        font_ref = writer._add_object(font)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font_ref})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 40 700 Td ({text}) Tj ET'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def docx_bytes(text):
    output = BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('word/document.xml', '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + text + '</w:t></w:r></w:p></w:body></w:document>')
    return output.getvalue()


TEXT = 'Employees receive 25 working days of annual leave per calendar year.'


@pytest.mark.parametrize('filename,content', [('policy.txt', TEXT.encode()), ('policy.md', TEXT.encode()), ('policy.docx', docx_bytes(TEXT)), ('policy.pdf', pdf_bytes(TEXT))])
def test_all_four_formats_extract_real_text(filename, content):
    assert TEXT in extract_text(filename, content)
    sections = extract_sections(filename, content)
    assert sections[0][0] == ('Page 1' if filename.endswith('.pdf') else 'Paragraph 1')


@pytest.mark.parametrize('filename,content', [('empty.txt', b''), ('short.txt', b'short'), ('scan.pdf', pdf_bytes()), ('broken.pdf', b'not a valid pdf'), ('broken.docx', b'not a zip'), ('binary.txt', b'\xff'*100), ('script.exe', TEXT.encode())])
def test_invalid_or_unusable_uploads_rejected(filename, content):
    with pytest.raises(ValueError):
        extract_sections(filename, content)


def test_pdf_encryption_rejected():
    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    writer.encrypt('secret')
    output = BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match='Encrypted'):
        extract_text('locked.pdf', output.getvalue())


def test_xml_entity_rejected():
    output = BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('word/document.xml', '<!DOCTYPE x [<!ENTITY x "entity">]><document>&x;</document>')
    with pytest.raises(ValueError, match='entity'):
        extract_text('unsafe.docx', output.getvalue())


def test_character_limit_and_chunk_coverage():
    with pytest.raises(ValueError, match='200,000'):
        extract_text('huge.txt', b'word '*40001)
    text = ' '.join(f'w{i}' for i in range(450))
    chunks = chunk_text(text)
    assert len(chunks) == 4
    assert chunks[0].split()[-30:] == chunks[1].split()[:30]
    assert chunks[-1].endswith('w449')
    assert chunk_text('') == []
    with pytest.raises(ValueError):
        chunk_text('hello', size=30, overlap=30)


def answer(text=TEXT, source='S1', quote=TEXT, insufficient=False):
    return GroundedAnswer(answer=text, citations=[{'source_id': source, 'quote': quote}], insufficient_evidence=insufficient)


SOURCES = [{'source_id': 'S1', 'text': TEXT, 'document_id': 'doc-1', 'locator': 'Page 1'}]


def test_valid_quote_and_numeric_support():
    result = validate_answer(answer(), SOURCES)
    assert not result['insufficient_evidence']
    assert result['checks']['citations_valid']


@pytest.mark.parametrize('candidate', [answer(source='S999'), answer(quote='Employees receive 50 days of paid leave.'), answer(text='Employees receive 99 working days of annual leave.'), answer(insufficient=True)])
def test_fabricated_citation_number_and_abstention_fail_closed(candidate):
    result = validate_answer(candidate, SOURCES)
    assert result['insufficient_evidence'] and not result['citations']


def test_no_citation_cannot_be_presented_as_grounded():
    result = validate_answer(GroundedAnswer(answer=TEXT, citations=[], insufficient_evidence=False), SOURCES)
    assert result['insufficient_evidence']


def test_numeric_formatting_does_not_cause_false_abstention():
    source = {'source_id': 'S1', 'text': 'The purchase limit is AED 5000 and the meal allowance is AED 150.'}
    candidate = answer(text='The purchase limit is AED 5,000. The meal allowance is AED 150.00.', quote=source['text'])
    assert not validate_answer(candidate, [source])['insufficient_evidence']


@pytest.mark.parametrize('text', ['Employees receive 99days of leave.', 'The annual leave payment is AED9999.', 'Employees receive -25 working days of leave.'])
def test_adjacent_units_and_signs_do_not_bypass_numeric_guard(text):
    assert validate_answer(answer(text=text), SOURCES)['insufficient_evidence']


def test_adjacent_currency_units_with_supported_number_are_valid():
    source = {'source_id': 'S1', 'text': 'The purchase limit is AED5000 and the meal allowance is AED150.'}
    assert not validate_answer(answer(text='The purchase limit is AED 5,000.', quote=source['text']), [source])['insufficient_evidence']


def test_dominant_process_source_excludes_unrelated_manager_responsibility():
    travel = {'source_id': 'S1', 'document_id': 'travel', 'text': 'Finance reviews receipts before reimbursement. The line manager approves the business purpose before travel.'}
    leave = {'source_id': 'S2', 'document_id': 'leave', 'text': 'The line manager approves annual leave. Request it before the start date.'}
    assert focus_sources([travel, leave], 'Who reviews receipts before reimbursement, and what does the line manager approve?') == [travel]


def test_focus_retains_similarly_relevant_conflicting_policies():
    sources = [{'source_id': 'S1', 'document_id': 'old', 'text': 'Permanent employees receive 25 working days of annual leave.'}, {'source_id': 'S2', 'document_id': 'conflict', 'text': 'Permanent employees receive 30 working days of annual leave.'}]
    assert focus_sources(sources, 'How many working days of annual leave do permanent employees receive?') == sources


def test_focus_retains_multiple_topics_and_low_overlap_queries():
    sources = [{'source_id': 'S1', 'document_id': 'leave', 'text': 'Annual leave entitlement is 25 working days.'}, {'source_id': 'S2', 'document_id': 'travel', 'text': 'Domestic meal reimbursement requires itemized receipts.'}]
    assert focus_sources(sources, 'Compare annual leave entitlement and domestic meal reimbursement receipts.') == sources
    assert focus_sources(sources, 'Explain the rules.') == sources


def test_focus_keeps_retrieved_exception_chunks_from_selected_document():
    sources = [{'source_id': 'S1', 'document_id': 'travel', 'text': 'Finance reviews receipts before reimbursement. The line manager approves business purpose before travel.'}, {'source_id': 'S2', 'document_id': 'travel', 'text': 'Exception: contractors use a separate workflow.'}, {'source_id': 'S3', 'document_id': 'leave', 'text': 'The line manager approves annual leave before it starts.'}]
    assert focus_sources(sources, 'Who reviews receipts before reimbursement, and what does the line manager approve?') == sources[:2]
