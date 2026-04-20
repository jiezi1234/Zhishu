import sys
import PyPDF2

def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_pdf.py <pdf_path>")
        return
    pdf_path = sys.argv[1]
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        num_pages = len(reader.pages)
        print(f"Number of pages: {num_pages}")
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            print(f"--- Page {i+1} ---")
            print(text.strip()[:100] + "...")

if __name__ == "__main__":
    main()
