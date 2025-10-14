from openai import OpenAI

from utils.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)
r = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "pong만 한 단어로 답해줘"}],
    temperature=0.0,
)
print(r.choices[0].message.content.strip())
