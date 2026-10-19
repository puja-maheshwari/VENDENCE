"""Generate professional, visibly labeled fictional PDFs; requires ReportLab.

No bank logos, official seals, signatures or registry authentication are added.
This optional fixture authoring dependency is not required to run VENDENCE.
"""
from pathlib import Path
from decimal import Decimal
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.testing_cases import TESTING_CASES, COMMON


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "testing")
    parser.add_argument("--overwrite", action="store_true", help="Replace only the six generated sample PDFs")
    args = parser.parse_args()
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from xml.sax.saxutils import escape
    width, height = A4
    left, right = 42, width - 42
    usable = right - left
    ink, muted, line = HexColor("#192938"), HexColor("#5D6974"), HexColor("#D7DEE5")
    regular = ParagraphStyle("body", fontName="Helvetica", fontSize=9, leading=13, textColor=ink)
    bold = ParagraphStyle("bold", parent=regular, fontName="Helvetica-Bold")

    def paragraph(text, heavy=False):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), bold if heavy else regular)

    def start(path, accent):
        path.parent.mkdir(parents=True, exist_ok=True)
        pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
        pdf.setTitle(path.stem.replace("_", " ") + " | Fictional demonstration copy")
        pdf.setAuthor("VENDENCE demonstration fixtures")
        pdf.setSubject("Fictional sample. Not issued by a government or bank.")
        pdf.setFillColor(HexColor("#F3F5F7"));pdf.rect(0, height-30, width, 30, fill=1, stroke=0)
        pdf.setFillColor(accent);pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(left, height-19, "SAMPLE - DEMONSTRATION ONLY")
        pdf.setFillColor(muted);pdf.setFont("Helvetica", 8)
        pdf.drawRightString(right, height-19, "FICTIONAL DETAILS")
        return pdf

    def footer(pdf):
        pdf.setStrokeColor(line);pdf.line(left, 62, right, 62)
        pdf.setFillColor(muted);pdf.setFont("Helvetica", 7.5)
        pdf.drawString(left, 47, "Sample - demonstration only. Fictional entity, identifiers, account and transactions.")
        pdf.drawString(left, 35, "Not issued by a government or bank. Not valid as registration or banking evidence.")
        pdf.drawRightString(right, 35, "Page 1 of 1")
        pdf.showPage();pdf.save()

    def table(pdf, rows, widths, top, header=False, heights=None):
        cells=[[paragraph(value, heavy=(header and i==0)) for value in row] for i,row in enumerate(rows)]
        t=Table(cells,colWidths=widths,rowHeights=heights,hAlign="LEFT")
        style=[("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),10),
               ("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),9),
               ("BOTTOMPADDING",(0,0),(-1,-1),9),("LINEBELOW",(0,0),(-1,-1),.45,line)]
        if header:style += [("BACKGROUND",(0,0),(-1,0),HexColor("#EDF1F5"))]
        t.setStyle(TableStyle(style));_,h=t.wrap(usable, height);t.drawOn(pdf,left,top-h)
        return top-h

    def heading(pdf, kicker, title, accent):
        pdf.setFillColor(accent);pdf.setFont("Helvetica-Bold",10);pdf.drawString(left,height-62,kicker)
        pdf.setFillColor(ink);pdf.setFont("Helvetica-Bold",23);pdf.drawString(left,height-95,title)

    def gst(path, data, number):
        navy=HexColor("#173D62");pdf=start(path,navy)
        heading(pdf,"GOODS AND SERVICES TAX  |  FORM GST REG-06","Registration Certificate",navy)
        pdf.setFillColor(muted);pdf.setFont("Helvetica",9)
        pdf.drawString(left,height-117,"Registration particulars")
        pdf.drawRightString(right,height-117,"Sample reference: DEMO-GST-00"+str(number))
        pdf.setFillColor(HexColor("#EDF3F8"));pdf.roundRect(left,height-175,usable,39,5,fill=1,stroke=0)
        pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",12);pdf.drawString(left+12,height-160,"GSTIN   "+data["tax_id"])
        rows=[
            ["1", "Legal name",COMMON["vendor_name"]],
            ["2", "Trade name","Blue Orchid Supplies"],
            ["3", "Constitution of business","Private Limited Company"],
            ["4", "Principal place of business","12 Demonstration Park,\nBengaluru, Karnataka - 560001"],
            ["5", "Date of registration","01 October 2026"],
            ["6", "Registration type","Regular"],
            ["7", "State / jurisdiction","Karnataka (29) / Sample Bengaluru jurisdiction"],
            ["8", "Period of validity","From 01 October 2026 / No expiry specified"],
        ]
        end=table(pdf,rows,[30,170,usable-200],height-195)
        pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",10);pdf.drawString(left,end-29,"BUSINESS PARTICULARS")
        end=table(pdf,[["PAN",data["tax_id"][2:12]],["Nature of business","Wholesale supply of packaging materials"],
                       ["Additional places of business","None listed in this sample"]],[200,usable-200],end-42)
        pdf.setFillColor(muted);pdf.setFont("Helvetica",8)
        pdf.drawString(left,end-30,"Prepared as a sample registration document for a software workflow demonstration.")
        footer(pdf)

    def bank(path, data):
        icici=data["bank_name"]=="ICICI Bank"
        accent=HexColor("#A74118" if icici else "#8A1B4C")
        bank_name="ICICI Bank Limited" if icici else "Axis Bank Limited"
        pdf=start(path,accent);heading(pdf,bank_name.upper(),"Account Statement",accent)
        pdf.setFillColor(muted);pdf.setFont("Helvetica",9)
        pdf.drawString(left,height-118,"Statement period: 01 September 2026 - 30 September 2026")
        pdf.drawRightString(right,height-135,"Currency: INR")
        rows=[["Account holder",COMMON["vendor_name"]],["Account number",data["bank_account_number"]],
              ["Account type / currency","Current Account / INR"],["IFSC",data["ifsc_code"]],
              ["Branch","Sample Operations Branch, Bengaluru"],["Correspondence address","12 Demonstration Park, Bengaluru, Karnataka - 560001"]]
        end=table(pdf,rows,[160,usable-160],height-151)
        pdf.setFillColor(accent);pdf.setFont("Helvetica-Bold",10);pdf.drawString(left,end-28,"TRANSACTION DETAILS")
        ledger=[["Date","Description / reference","Debit (INR)","Credit (INR)","Balance (INR)"],
                ["01 Sep","Opening balance","-","-","125,000.00"],
                ["02 Sep","Customer receipt / DEMO-01","-","48,000.00","173,000.00"],
                ["05 Sep","Supplier payment / DEMO-02","12,500.00","-","160,500.00"],
                ["11 Sep","NEFT receipt / DEMO-03","-","32,000.00","192,500.00"],
                ["18 Sep","Office rent / DEMO-04","18,000.00","-","174,500.00"],
                ["24 Sep","Operating expense / DEMO-05","7,500.00","-","167,000.00"],
                ["30 Sep","Invoice collection / DEMO-06","-","23,500.00","190,500.00"]]
        end=table(pdf,ledger,[49,180,89,89,usable-407],end-41,header=True)
        end=table(pdf,[["Opening balance","125,000.00"],["Total debit / total credit","38,000.00 / 103,500.00"],
                       ["Closing balance","190,500.00"]],[usable-160,160],end-18)
        assert Decimal('125000')+Decimal('103500')-Decimal('38000')==Decimal('190500')
        assert end>90,'Statement content overlaps footer'
        footer(pdf)

    def invoice(path,data):
        accent=HexColor("#235A5C");pdf=start(path,accent)
        heading(pdf,"BLUE ORCHID SUPPLIES PRIVATE LIMITED","Tax Invoice",accent)
        pdf.setFillColor(muted);pdf.setFont("Helvetica",9)
        pdf.drawString(left,height-118,"12 Demonstration Park, Bengaluru, Karnataka - 560001")
        pdf.drawString(left,height-134,"Supplier GSTIN: "+data["tax_id"])
        rows=[["Invoice number","DEMO-INV-2026-0142"],["Invoice date / due date","26 September 2026 / 10 October 2026"],
              ["Bill to","Cedar Peak Retail Private Limited\n24 Sample Avenue, Bengaluru, Karnataka - 560001"],
              ["Place of supply","Karnataka (29)"]]
        end=table(pdf,rows,[160,usable-160],height-158)
        items=[["Description","Qty","Rate (INR)","Taxable (INR)","GST (INR)"],
               ["Packaging materials - sample order","10","1,000.00","10,000.00","1,800.00"],
               ["Delivery and handling - sample charge","1","2,000.00","2,000.00","360.00"]]
        end=table(pdf,items,[195,50,85,95,usable-425],end-22,header=True)
        end=table(pdf,[["Taxable amount","12,000.00"],["CGST / SGST (illustrative)","1,080.00 / 1,080.00"],
                       ["Invoice total (INR)","14,160.00"]],[usable-160,160],end-18)
        pdf.setFillColor(accent);pdf.setFont("Helvetica-Bold",10);pdf.drawString(left,end-28,"PAYMENT DETAILS")
        end=table(pdf,[["Bank","Axis Bank Limited"],["Account holder",COMMON["vendor_name"]],
                       ["Account number / IFSC",data["bank_account_number"]+" / "+data["ifsc_code"]]],[160,usable-160],end-42)
        pdf.setFillColor(muted);pdf.setFont("Helvetica",8)
        pdf.drawString(left,end-30,"All goods, amounts and payment details on this invoice are fictional sample data.")
        assert end>110,'Invoice content overlaps footer'
        footer(pdf)

    for number,case in enumerate(TESTING_CASES,1):
        directory=args.output/case["folder"]
        if not args.overwrite and ((directory/case["gst_file"]).exists() or (directory/case["bank_file"]).exists()):
            parser.error("Destination already contains these PDFs; archive it before regenerating.")
        if case["expected"]=="PENDING":invoice(directory/case["gst_file"],case["data"])
        else:gst(directory/case["gst_file"],case["data"],number)
        bank(directory/case["bank_file"],case["data"])
    print("Created six fictional PDFs in three folders:",args.output)


if __name__=="__main__":
    main()
