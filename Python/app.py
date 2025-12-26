from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
from enum import Enum
import sqlite3
from contextlib import closing
import os

# ------------------------------------
# Configuração básica
# ------------------------------------
app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "controle_gastos.db")


# ------------------------------------
# Categorias (adaptadas do types.ts)
# ------------------------------------
class Category(str, Enum):
    RECARGA = "Recarga"
    SUPERMERCADO = "Supermercado"
    LANCHES = "Lanches"
    ENSINO = "Ensino"
    FARMACIA = "Farmácia"
    CARTAO = "Parcelas Cartão"
    CONTAS_CASA = "Contas de Casa"
    THAIS = "Thais"
    OUTROS = "Outros"


# ------------------------------------
# Funções auxiliares de banco de dados
# ------------------------------------
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,            -- 'income' ou 'expense'
                category TEXT,                 -- obrigatório para expense
                source TEXT,                   -- descrição ou origem
                value REAL NOT NULL,
                date TEXT NOT NULL             -- ISO: YYYY-MM-DD
            )
            """
        )
        conn.commit()


# ------------------------------------
# Lógica de resumo financeiro
# ------------------------------------
def get_all_entries():
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM entries ORDER BY date DESC, id DESC")
        return cur.fetchall()


def get_current_month_key():
    today = datetime.today()
    return today.strftime("%Y-%m")  # ex: 2025-12


def compute_summary(entries, month_key=None):
    """
    entries: lista de linhas do banco
    month_key: 'YYYY-MM' -> se None, usa mês atual
    """
    if month_key is None:
        month_key = get_current_month_key()

    total_income = 0.0
    total_expenses = 0.0
    category_totals = {cat.value: 0.0 for cat in Category}

    for e in entries:
        date_str = e["date"]
        if not date_str:
            continue
        if not date_str.startswith(month_key):
            # ignora meses diferentes do selecionado
            continue

        value = float(e["value"])
        if e["type"] == "income":
            total_income += value
        elif e["type"] == "expense":
            total_expenses += value
            cat = e["category"] or Category.OUTROS.value
            if cat not in category_totals:
                category_totals[cat] = 0.0
            category_totals[cat] += value

    balance = total_income - total_expenses

    return {
        "month_key": month_key,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": balance,
        "category_totals": category_totals,
    }


# ------------------------------------
# Rotas
# ------------------------------------
@app.route("/", methods=["GET"])
def index():
    entries = get_all_entries()
    month_key = request.args.get("month") or get_current_month_key()
    summary = compute_summary(entries, month_key=month_key)

    # Descobrir todos os meses existentes no banco para um seletor simples
    months = sorted(
        {row["date"][:7] for row in entries if row["date"]}, reverse=True
    )

    return render_template(
        "index.html",
        entries=entries,
        summary=summary,
        categories=[c.value for c in Category],
        current_month=month_key,
        months=months,
    )


@app.route("/add", methods=["POST"])
def add_entry():
    entry_type = request.form.get("type")  # 'income' ou 'expense'
    raw_value = (request.form.get("value") or "").replace(",", ".")
    description = request.form.get("description") or ""
    category = request.form.get("category") or None
    date_str = request.form.get("date") or datetime.today().strftime("%Y-%m-%d")

    try:
        value = float(raw_value)
    except ValueError:
        # valor inválido, volta pra página
        return redirect(url_for("index"))

    if entry_type not in ("income", "expense"):
        return redirect(url_for("index"))

    # Para income, categoria não é obrigatória
    if entry_type == "expense" and not category:
        category = Category.OUTROS.value

    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO entries (type, category, source, value, date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (entry_type, category, description, value, date_str),
        )
        conn.commit()

    return redirect(url_for("index"))


@app.route("/delete/<int:entry_id>", methods=["POST"])
def delete_entry(entry_id):
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        conn.commit()
    return redirect(url_for("index"))


# ------------------------------------
# Inicialização
# ------------------------------------
if __name__ == "__main__":
    init_db()
    # debug=True é só para desenvolvimento
    app.run(debug=True)
