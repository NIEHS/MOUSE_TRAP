# NIEHS Neurobehavioral Circuits Group Code

This repository houses various software tools and code developed for and by the Neurobehavioral Circuits Group. It currently includes:

- [**File Converter**:](#file-converter) A multi-format file converter built with PyQt6.

## About the Neurobehavioral Circuits Group

Led by Dr. Julieta Lischinsky, the group investigates the developmental and circuit mechanisms underlying social behaviors and how these processes are affected by environmental stressors.

## File Converter

Located in the `File Converter` folder, this tool provides:

- **Video Conversion:**  
  Converts `.seq` files to `.mp4` (with optional annotation-based clipping) and supports other video formats via FFmpeg.
- **Image Conversion:**  
  Converts between common image formats and allows image-to-PDF conversion using Pillow.
- **Document Conversion:**  
  Handles PDF, DOCX, and TXT conversions via pdf2image and pypandoc.
- **Graphical User Interface:**  
  Developed in PyQt6 for easy file selection, option configuration, and progress monitoring.

## Prerequisites

- **Python 3.13.1+**
- **Dependencies:** PyQt6, OpenCV, Pillow, pdf2image, pypandoc, docx2pdf
- **External Tools:** FFmpeg, Poppler (for pdf2image), Pandoc (for pypandoc)

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/rmharp/NBCG.git
   ```

2. **Navigate to the Project Directory:**

   ```bash
   cd NBCG
   ```

3. **Install Dependencies:**
   
   ```bash
   pip install -r requirements.txt
   ```
   
   Otherwise, install the required packages individually.

## Usage

To run the File Converter tool:

```bash
python "File Converter/main.py"
```

A GUI will launch for file selection, conversion options, and progress monitoring.
