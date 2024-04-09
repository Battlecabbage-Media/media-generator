FROM python:3.11 AS backend
WORKDIR /app/
COPY media_generator.py .
COPY requirements.txt .
COPY templates/ templates/
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Install MS Fonts
FROM backend AS msfonts
RUN echo "deb http://deb.debian.org/debian bookworm contrib non-free" > /etc/apt/sources.list.d/contrib.list && apt-get update && ACCEPT_EULA=Y apt install -y ttf-mscorefonts-installer

# Stage 3: Run the generator
FROM msfonts AS final
WORKDIR /app
RUN mkdir outputs
VOLUME /outputs
RUN chmod +x media_generator.py
CMD ["python", "media_generator.py"]