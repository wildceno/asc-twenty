FROM python:3.12-slim
WORKDIR /app
COPY ascendia_motor ./ascendia_motor
# Sırlar salt okunur bağlanır; konteyner sunucu kullanıcısının kimliğiyle çalışır (compose: user)
CMD ["python3", "-u", "-m", "ascendia_motor"]
