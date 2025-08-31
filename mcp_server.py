import os
import matplotlib
matplotlib.use("Agg")
from flask import Flask, request, jsonify
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO

app = Flask(__name__)

def plot_to_base64():
    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

def generate_result(df, tool, params):
    column = params.get("column")
    x_col = params.get("x")
    y_col = params.get("y")
    result = {"image": None, "data_summary": {}, "extra": {}}
    try:
        if tool == "summary":
            result["data_summary"] = df.describe(include="all").to_dict()
        elif tool == "columns":
            result["data_summary"] = list(df.columns)
        elif tool == "head":
            result["data_summary"] = df.head().to_dict()
        elif tool == "tail":
            result["data_summary"] = df.tail().to_dict()
        elif tool == "info":
            import io
            buf = io.StringIO()
            df.info(buf=buf)
            result["data_summary"] = buf.getvalue()
        elif tool == "shape":
            result["data_summary"] = {"rows": df.shape[0], "columns": df.shape[1]}
        elif tool == "missing":
            result["data_summary"] = df.isnull().sum().to_dict()
        elif tool == "unique_counts":
            result["data_summary"] = {col: df[col].nunique() for col in df.columns}
        elif tool == "top_values":
            result["data_summary"] = {col: df[col].value_counts().head(5).to_dict() for col in df.columns}
        elif tool == "drop_duplicates":
            result["data_summary"] = df.drop_duplicates().to_dict()
        elif tool == "histogram" and column:
            plt.figure()
            df[column].hist(bins=30)
            plt.title(f"Histogram of {column}")
            result["image"] = plot_to_base64()
            result["data_summary"] = {
                "min": float(df[column].min()),
                "max": float(df[column].max()),
                "mean": float(df[column].mean()),
                "median": float(df[column].median()),
                "std": float(df[column].std()),
                "quartiles": df[column].quantile([0.25,0.5,0.75]).to_dict()
            }
        elif tool == "boxplot" and column:
            plt.figure()
            sns.boxplot(x=df[column])
            plt.title(f"Boxplot of {column}")
            result["image"] = plot_to_base64()
            q = df[column].quantile([0.25,0.5,0.75])
            result["data_summary"] = {"min": float(df[column].min()), "Q1": float(q[0.25]),
                                      "median": float(q[0.5]), "Q3": float(q[0.75]),
                                      "max": float(df[column].max()), "IQR": float(q[0.75]-q[0.25])}
        elif tool == "scatter" and x_col and y_col:
            plt.figure()
            plt.scatter(df[x_col], df[y_col])
            plt.title(f"{x_col} vs {y_col}")
            result["image"] = plot_to_base64()
            corr = df[[x_col, y_col]].corr().iloc[0,1]
            result["data_summary"] = {
                "x_mean": float(df[x_col].mean()), "y_mean": float(df[y_col].mean()),
                "x_std": float(df[x_col].std()), "y_std": float(df[y_col].std()),
                "correlation": float(corr)
            }
        elif tool == "heatmap":
            plt.figure(figsize=(8,6))
            corr = df.corr(numeric_only=True)
            sns.heatmap(corr, annot=True, cmap="coolwarm")
            plt.title("Correlation Heatmap")
            result["image"] = plot_to_base64()
            result["data_summary"] = corr.round(2).to_dict()
        elif tool == "pairplot":
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if numeric_cols:
                sns.pairplot(df[numeric_cols])
                result["image"] = plot_to_base64()
                result["data_summary"] = df[numeric_cols].describe().to_dict()
        elif tool == "barplot" and column:
            plt.figure()
            sns.countplot(y=column, data=df)
            plt.title(f"Barplot of {column}")
            result["image"] = plot_to_base64()
            result["data_summary"] = df[column].value_counts().to_dict()
        elif tool == "lineplot" and x_col and y_col:
            plt.figure()
            sns.lineplot(x=df[x_col], y=df[y_col])
            plt.title(f"{y_col} over {x_col}")
            result["image"] = plot_to_base64()
            result["data_summary"] = {
                "x_min": float(df[x_col].min()), "x_max": float(df[x_col].max()),
                "y_min": float(df[y_col].min()), "y_max": float(df[y_col].max()),
                "y_mean": float(df[y_col].mean())
            }
        elif tool == "missing_visual":
            plt.figure(figsize=(8,6))
            sns.heatmap(df.isnull(), cbar=False, cmap="viridis")
            plt.title("Missing Data Heatmap")
            result["image"] = plot_to_base64()
            result["data_summary"] = df.isnull().sum().to_dict()
        elif tool == "outlier_detection" and column:
            q1 = df[column].quantile(0.25)
            q3 = df[column].quantile(0.75)
            iqr = q3 - q1
            outliers = df[(df[column] < q1 - 1.5*iqr) | (df[column] > q3 + 1.5*iqr)]
            result["data_summary"] = {"Q1": float(q1), "Q3": float(q3), "IQR": float(iqr), "outlier_count": len(outliers)}
            result["extra"]["outliers"] = outliers.to_dict()
        else:
            result["data_summary"] = {"error": "Unknown tool or missing parameters"}
    except Exception as e:
        result["data_summary"] = {"error": str(e)}
    return result

@app.route('/analyze', methods=['POST'])
def analyze_route():
    file = request.files.get('file')
    tool = request.form.get('tool')
    params = request.form.to_dict()
    if not file or not tool:
        return jsonify({"error": "Missing file or tool"}), 400
    df = pd.read_csv(file)
    result = generate_result(df, tool, params)
    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(port=5001, debug=True)
