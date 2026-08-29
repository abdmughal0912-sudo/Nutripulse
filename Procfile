web: streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true
api: uvicorn api:app --host=0.0.0.0 --port=${API_PORT:-8000}
