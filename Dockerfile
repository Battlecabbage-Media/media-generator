FROM python:3.11-slim AS msfonts
WORKDIR /app
RUN echo "deb http://deb.debian.org/debian bookworm contrib non-free" > /etc/apt/sources.list.d/contrib.list && apt-get update && ACCEPT_EULA=Y apt install -y ttf-mscorefonts-installer

# Stage 2: Install python requirements
FROM msfonts AS backend
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Run the generator
FROM backend AS final
WORKDIR /app
COPY media_generator.py .
COPY templates/ templates/
RUN mkdir outputs
VOLUME /app/outputs
RUN chmod +x media_generator.py
CMD ["python", "media_generator.py"]