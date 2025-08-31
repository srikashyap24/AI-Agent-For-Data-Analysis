import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, render_template, redirect, url_for, jsonify
import requests
import openai
import json
import pandas as pd
from markdown import markdown

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---------------------------
# MCP Tool Runner
# ---------------------------
def run_mcp_tool_with_params(tool_name, filepath, params=None):
    url = 'http://localhost:5001/analyze'
    with open(filepath, 'rb') as f:
        files = {'file': f}
        data = {'tool': tool_name}
        if params:
            data.update(params)
        response = requests.post(url, files=files, data=data)
    if response.status_code == 200:
        return response.json().get('result', {})
    return {'error': 'MCP server error'}

# ---------------------------
# Routes
# ---------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            return redirect(url_for('analyze', filename=file.filename))
    return render_template('index.html')

@app.route('/analyze/<filename>', methods=['GET', 'POST'])
def analyze(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df = pd.read_csv(filepath)

    if request.method == 'POST':
        question = request.form['question']

        # ---------------------------
        # 1. Ask LLM to select tool and column(s)
        # ---------------------------
        tools = [
            'summary', 'columns', 'head', 'missing', 'value_counts',
            'correlation', 'describe_numeric', 'histogram', 'boxplot', 'heatmap',
            'scatter', 'barplot', 'lineplot', 'missing_visual', 'outlier_detection'
        ]
        prompt = (
            f"You are a data analysis agent. Given the columns: {list(df.columns)}, "
            f"and the question: '{question}', select the best tool from this list: {tools}. "
            "If a visualization tool is selected, specify column(s) to use. "
            "Respond in JSON format: { 'tool': tool_name, 'column': column_name (if needed), 'x': x_column, 'y': y_column }."
        )
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            llm_reply = response.choices[0].message.content.strip()
            selection = json.loads(llm_reply)
            tool_name = selection.get('tool', '').lower()
            column = selection.get('column', None)
            x_col = selection.get('x', None)
            y_col = selection.get('y', None)
        except Exception:
            tool_name = llm_reply.lower()
            column = None
            x_col = None
            y_col = None

        # ---------------------------
        # 2. Run MCP tool
        # ---------------------------
        params = {}
        if column:
            params['column'] = column
        if x_col:
            params['x'] = x_col
        if y_col:
            params['y'] = y_col

        result = run_mcp_tool_with_params(tool_name, filepath, params)

        # ---------------------------
        # 3. Ask LLM to summarize insights
        # ---------------------------
        summary_prompt = f"""
        You are a data analyst AI. The tool '{tool_name}' was run on the dataset.
        Column(s): {column if column else ''}, X: {x_col if x_col else ''}, Y: {y_col if y_col else ''}
        Numeric Summary / Stats: {result.get('data_summary', {})}
        Extra Info: {result.get('extra', {})}
        Explain clearly the insights in markdown with bullet points.
        If there is a plot image, consider distribution, trends, correlations, outliers, etc.
        """
        summary_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": summary_prompt}]
        )
        summary = summary_response.choices[0].message.content
        summary_html = markdown(summary)

        return render_template('result.html', result=result, summary=summary_html, filename=filename)

    return render_template('analyze.html', columns=list(df.columns), filename=filename)

@app.route('/reset', methods=['GET'])
def reset():
    # Remove uploaded files and reset session if needed
    return redirect(url_for('index'))

# ---------------------------
# Run App
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)
