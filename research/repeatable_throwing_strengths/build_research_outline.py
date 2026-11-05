"""Build the plain numbered seminar outline with the bundled python-docx runtime."""
from pathlib import Path
import json
import shutil
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parent
doc = Document()
sec = doc.sections[0]
sec.page_width = Inches(8.5)
sec.page_height = Inches(11)
sec.top_margin = sec.bottom_margin = Inches(1)
sec.left_margin = sec.right_margin = Inches(1)

for style in doc.styles:
    for border in list(style.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
for name in ['Normal', 'Title', 'Heading 1']:
    style = doc.styles[name]
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.font.bold = name in ['Title', 'Heading 1']
    style.font.italic = False
    fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    for key in ['asciiTheme', 'hAnsiTheme', 'csTheme', 'eastAsiaTheme']:
        fonts.attrib.pop(qn('w:' + key), None)
    for key in ['ascii', 'hAnsi', 'cs', 'eastAsia']:
        fonts.set(qn('w:' + key), 'Times New Roman')
    fmt = style.paragraph_format
    fmt.line_spacing = 1.0
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(6)
    fmt.widow_control = True
    fmt.keep_with_next = name != 'Normal'
doc.styles['Heading 1'].paragraph_format.space_before = Pt(18)
doc.styles['Heading 1'].paragraph_format.space_after = Pt(8)

# Native Word numbering keeps the outline editable without nested lists.
numbering = doc.part.numbering_part.element
abstract_id = max(int(x.get(qn('w:abstractNumId'))) for x in numbering.findall(qn('w:abstractNum'))) + 1
num_id = max(int(x.get(qn('w:numId'))) for x in numbering.findall(qn('w:num'))) + 1
abstract = OxmlElement('w:abstractNum')
abstract.set(qn('w:abstractNumId'), str(abstract_id))
level = OxmlElement('w:lvl')
level.set(qn('w:ilvl'), '0')
for tag, value in [('start', '1'), ('numFmt', 'decimal'), ('lvlText', '%1.'), ('suff', 'space')]:
    element = OxmlElement('w:' + tag)
    element.set(qn('w:val'), value)
    level.append(element)
abstract.append(level)
numbering.append(abstract)
num = OxmlElement('w:num')
num.set(qn('w:numId'), str(num_id))
ref = OxmlElement('w:abstractNumId')
ref.set(qn('w:val'), str(abstract_id))
num.append(ref)
numbering.append(num)

outline = json.loads((ROOT / 'huck_outline_content.json').read_text())
doc.core_properties.author = 'Theodore Taussig'
doc.core_properties.title = outline['title']
doc.core_properties.subject = 'Computer science research seminar'
doc.add_paragraph(outline['title'], 'Title')
doc.add_paragraph('Theodore Taussig')

sections = outline['sections']

for label, paragraphs in sections:
    heading = doc.add_paragraph(label, 'Heading 1')
    if label == outline.get('page_break_before'):
        heading.paragraph_format.page_break_before = True
    props = heading._p.get_or_add_pPr().get_or_add_numPr()
    props.get_or_add_ilvl().val = 0
    props.get_or_add_numId().val = num_id
    for text in paragraphs:
        doc.add_paragraph(text)

for note in outline.get('source_notes', []):
    p = doc.add_paragraph(note['text'])
    p.paragraph_format.space_before = Pt(12)
    if note.get('url'):
        link = OxmlElement('w:hyperlink')
        link.set(qn('r:id'), p.part.relate_to(note['url'], RT.HYPERLINK, is_external=True))
        run = OxmlElement('w:r')
        props = OxmlElement('w:rPr')
        fonts = OxmlElement('w:rFonts')
        for key in ['ascii', 'hAnsi']:
            fonts.set(qn('w:' + key), 'Times New Roman')
        props.append(fonts)
        size = OxmlElement('w:sz')
        size.set(qn('w:val'), '24')
        props.append(size)
        underline = OxmlElement('w:u')
        underline.set(qn('w:val'), 'single')
        props.append(underline)
        run.append(props)
        text = OxmlElement('w:t')
        text.text = note['link_label']
        run.append(text)
        link.append(run)
        p._p.append(link)

out = ROOT / 'Repeatable_throwing_strengths_research_outline.docx'
doc.save(out)
delivery = Path(outline.get('delivery_path', out))
if delivery != out:
    delivery.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, delivery)
print(json.dumps({'output': str(delivery), 'updated_existing_outline': str(out), 'words': sum(len(p.text.split()) for p in doc.paragraphs)}))
