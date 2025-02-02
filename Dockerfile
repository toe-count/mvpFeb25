# Use a lightweight Python base image
FROM python:3.9-slim

# Create and switch to /app directory
WORKDIR /app

# 1) Copy and install Python dependencies
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 2) Copy the Flask code from backend/
COPY backend/ /app

# 3) Copy your front-end file (index.html) into Flask's static folder
RUN mkdir -p /app/static
COPY index.html /app/static/index.html

# (Optional) If you have more front-end files (CSS/JS), copy them here too:
# COPY some-script.js /app/static/some-script.js
# COPY style.css /app/static/style.css

# 4) Expose the port that Gunicorn/Flask will listen on
EXPOSE 8000

# 5) Start Gunicorn, binding to port 8000, serving 'app:app'
#    (where `app` is your "app" object in `app.py`)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]