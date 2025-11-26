# Sentiment-Analysis-using-NLP-BERT-Hugging-Face-Transformer-
A complete NLP pipeline for extracting articles from URLs, cleaning text, performing linguistic analysis, and generating sentiment/readability metrics.

## 🚀 Features

📥 Read URLs from Input.xlsx

🌐 Scrape article content (title + body)

🧹 Clean HTML (remove scripts, headers, footers, ads)

🔤 Tokenize text into sentences & words

😊 Compute sentiment scores (positive/negative)

📊 Generate detailed NLP metrics

📝 Save extracted text in extracted_articles/

📦 Export results to Output.xlsx

## 📁 Project Structure
.
├── Input.xlsx
├── Final_Output_clean.xlsx
├── nlp_extractor.py
├── Untitled.ipynb
├── Output.xlsx
├── extracted_articles/
└── lexicons/ (optional)

## ⚙️ Installation

Install required dependencies:

pip install requests beautifulsoup4 lxml pandas openpyxl


## Optional lexicons (improves accuracy):

lexicons/
 ├── positive-words.txt
 ├── negative-words.txt
 └── stopwords.txt


If missing, fallback lexicons are used automatically.

## ▶️ How to Run

Basic command:

python nlp_extractor.py --input Input.xlsx --out Output.xlsx


## Optional:

python nlp_extractor.py --input Input.xlsx --out Output.xlsx --out_csv Output.csv --save_html

## 📊 Output Metrics Generated

Positive Score

Negative Score

Polarity

Subjectivity

Average Sentence Length

Percentage of Complex Words

Fog Index

Complex Word Count

Word Count

Syllables per Word

Personal Pronouns

Average Word Length

## 🧠 Processing Pipeline

Load URL list from Excel

Download webpage content

Remove noise (ads, scripts, navigation, etc.)

Extract title & main article text

Tokenize & clean text

Compute sentiment & readability metrics

Export final cleaned output to Excel

## 🛠️ Main Script

The core logic is in:

nlp_extractor.py

It handles:

URL fetching

HTML cleaning

Text extraction

NLP computation

Excel output generation
