FROM python:3.14-slim

# Install Tesseract OCR
RUN apt-get update && \
    apt-get install -y tesseract-ocr && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Create uploads folder
RUN mkdir -p uploads

# Start Flask using Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]