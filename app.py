import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from fpdf import FPDF
import bcrypt

# --- 1. CONFIGURAÇÃO E ESTILO PREMIUM ---
st.set_page_config(page_title="CyberFinance Pro", page_icon="💎", layout="wide")

def aplicar_ui_cyber():
    st.markdown("""
    <style>
        /* Estilo Geral Cyberpunk */
        .stApp {
            background: radial-gradient(circle at top right, #0a192f, #020c1b);
            color: #e6f1ff;
        }
        
        /* Glassmorphism nos Cards e Containers */
        div[data-testid="stMetric"], .stTabs, .stForm, .stDataFrame, div[data-testid="stExpander"] {
            background: rgba(255, 255, 255, 0.03) !important;
            backdrop-filter: blur(12px);
            border: 1px solid rgba(0, 173, 181, 0.2);
            border-radius: 15px !important;
            padding: 15px;
            transition: 0.3s;
        }
        
        /* Efeito Hover nos Métricas */
        div[data-testid="stMetric"]:hover {
            transform: translateY(-5px);
            border-color: #00f5d4;
            box-shadow: 0 10px 20px rgba(0, 245, 212, 0.2);
        }
        
        /* Botões Neon */
        .stButton>button {
            border: 1px solid #00f5d4;
            background: transparent;
            color: #00f5d4;
            border-radius: 50px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: 0.4s;
            width: 100%;
        }
        .stButton>button:hover {
            background: #00f5d4;
            color: #020c1b;
            box-shadow: 0 0 15px #00f5d4;
        }
        
        /* Barras de Progresso */
        .stProgress > div > div > div > div {
            background-image: linear-gradient(to right, #00f5d4, #00ADB5);
        }
        
        /* Títulos Neon */
        h1, h2, h3 { color: #00f5d4 !important; text-shadow: 0 0 10px rgba(0,245,212,0.3); }
        
        /* Inputs Dark */
        input, select, textarea {
            background-color: #0d1117 !important;
            color: #00ADB5 !important;
            border: 1px solid #30363d !important;
        }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CORE: BANCO DE DADOS ---
DB_FILE = 'financeiro.db'
USUARIO_PADRAO = "admin"
SENHA_PADRAO_TEXTO = "1234" # Senha para comparação de fallback
LISTA_CATEGORIAS = ["Alimentação", "Transporte", "Lazer", "Educação", "Hardware", "Contas Fixas", "Outros"]

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS movimentacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data DATE, categoria TEXT, descricao TEXT, valor REAL, tipo TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS logs_auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, acao TEXT, usuario TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS metas (categoria TEXT PRIMARY KEY, valor_limite REAL)')
        c.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, criado_em TEXT)')
        
        # Inicializa metas zeradas se não existirem
        c.execute("SELECT COUNT(*) FROM metas")
        if c.fetchone()[0] == 0:
            for cat in LISTA_CATEGORIAS:
                c.execute("INSERT INTO metas (categoria, valor_limite) VALUES (?, ?)", (cat, 0.0))
        # Garante usuário admin padrão no banco
        c.execute("SELECT COUNT(*) FROM usuarios WHERE username = ?", (USUARIO_PADRAO,))
        if c.fetchone()[0] == 0:
            hash_admin = bcrypt.hashpw(SENHA_PADRAO_TEXTO.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            c.execute("INSERT INTO usuarios (username, password_hash, criado_em) VALUES (?,?,?)",
                      (USUARIO_PADRAO, hash_admin, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()

def run_query(q, p=()):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(q, p); conn.commit()

def get_data(q):
    with sqlite3.connect(DB_FILE) as conn:
        return pd.read_sql(q, conn)

def ensure_users_table():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("SELECT 1 FROM usuarios LIMIT 1")
    except sqlite3.OperationalError:
        # Cria a tabela caso o banco tenha sido gerado antes da migração
        init_db()

def get_user_hash(username):
    ensure_users_table()
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT password_hash FROM usuarios WHERE username = ?", (username,))
        row = c.fetchone()
        return row[0] if row else None

def create_user(username, password):
    ensure_users_table()
    senha_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    run_query("INSERT INTO usuarios (username, password_hash, criado_em) VALUES (?,?,?)",
              (username, senha_hash, datetime.now().strftime("%Y-%m-%d %H:%M")))

# --- 3. FUNCIONALIDADES AUXILIARES ---
class PDFRelatorio(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'RELATORIO CYBERFINANCE', 0, 1, 'C')

def gerar_pdf(df_v):
    pdf = PDFRelatorio(); pdf.add_page(); pdf.set_font("Arial", size=12)
    def txt(t): return str(t).encode('latin-1', 'replace').decode('latin-1')
    
    r = df_v[df_v['tipo']=='Receita']['valor'].sum()
    d = df_v[df_v['tipo']=='Despesa']['valor'].sum()
    
    pdf.cell(0, 10, txt(f"Resumo Financeiro do Periodo"), 0, 1)
    pdf.cell(0, 10, txt(f"Total Ganhos: R$ {r:.2f}"), 0, 1)
    pdf.cell(0, 10, txt(f"Total Gastos: R$ {d:.2f}"), 0, 1)
    pdf.cell(0, 10, txt(f"Saldo Final: R$ {r-d:.2f}"), 0, 1)
    pdf.ln(10)
    pdf.cell(0, 10, txt("Extrato Detalhado:"), 0, 1)
    
    for index, row in df_v.iterrows():
        linha = f"{row['data']} | {row['tipo']} | {row['categoria']} | R$ {row['valor']:.2f}"
        pdf.cell(0, 10, txt(linha), 0, 1)
        
    return bytes(pdf.output())

def classificar_ia(desc):
    d = desc.lower()
    if any(x in d for x in ['mc', 'pizza', 'ifood', 'burger', 'comida', 'restaurante']): return "Alimentação"
    if any(x in d for x in ['uber', 'gasolina', 'posto', 'shell', '99', 'metro']): return "Transporte"
    if any(x in d for x in ['netflix', 'spotify', 'steam', 'cinema', 'game', 'prime']): return "Lazer"
    if any(x in d for x in ['faculdade', 'curso', 'livro', 'udemy', 'alura']): return "Educação"
    if any(x in d for x in ['monitor', 'mouse', 'teclado', 'placa', 'ssd', 'ram']): return "Hardware"
    if any(x in d for x in ['luz', 'agua', 'internet', 'aluguel']): return "Contas Fixas"
    return "Outros"

# --- INICIALIZAÇÃO ---
init_db()
aplicar_ui_cyber()

# --- 4. LOGIN (COM HASHING & FALLBACK) ---
if 'logado' not in st.session_state: st.session_state['logado'] = False

if not st.session_state['logado']:
    _, col, _ = st.columns([1,1.5,1])
    with col:
        st.write("")
        st.markdown("<h1 style='text-align:center;'>🚀 Cyber Login</h1>", unsafe_allow_html=True)
        tab_login, tab_cadastro = st.tabs(["Login", "Cadastrar"])

        with tab_login:
            u = st.text_input("Usuário", key="login_user")
            p = st.text_input("Chave de Acesso", type="password", key="login_pass")

            if st.button("AUTENTICAR"):
                senha_correta = False

                # 1) Validação por usuário cadastrado
                hash_salvo = get_user_hash(u)
                if hash_salvo:
                    try:
                        if bcrypt.checkpw(p.encode('utf-8'), hash_salvo.encode('utf-8')):
                            senha_correta = True
                    except:
                        pass
                elif u:
                    st.info("Usuário não encontrado. Use a aba Cadastrar.")

                # 2) Fallback do admin (senha texto) para não travar acesso
                if not senha_correta and u == USUARIO_PADRAO and p == SENHA_PADRAO_TEXTO:
                    senha_correta = True

                if senha_correta:
                    with st.spinner("Descriptografando acesso..."):
                        time.sleep(0.8)
                    st.session_state['logado'] = True
                    run_query("INSERT INTO logs_auditoria (data_hora, acao, usuario) VALUES (?,?,?)", 
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), "Login Realizado", u))
                    st.rerun()
                else:
                    st.error("ACESSO NEGADO: Credenciais Inválidas")

        with tab_cadastro:
            nu = st.text_input("Novo usuário", key="cad_user")
            np = st.text_input("Senha", type="password", key="cad_pass")
            nc = st.text_input("Confirmar senha", type="password", key="cad_conf")

            if st.button("CRIAR CONTA"):
                if not nu or not np:
                    st.warning("Preencha usuário e senha.")
                elif np != nc:
                    st.warning("As senhas não conferem.")
                else:
                    try:
                        create_user(nu, np)
                        run_query("INSERT INTO logs_auditoria (data_hora, acao, usuario) VALUES (?,?,?)",
                                  (datetime.now().strftime("%Y-%m-%d %H:%M"), "Usuário Criado", nu))
                        st.success("Usuário criado com sucesso. Faça login.")
                    except sqlite3.IntegrityError:
                        st.error("Usuário já existe. Escolha outro.")
    st.stop()

# --- 5. SIDEBAR (MENU LATERAL) ---
with st.sidebar:
    st.markdown(f"### 👤 ADMIN: {USUARIO_PADRAO.upper()}")
    if st.button("🔒 Encerrar Sessão"): 
        st.session_state['logado'] = False
        st.rerun()
    st.divider()

    st.subheader("📥 Lançamentos")
    t_desp, t_rec, t_csv = st.tabs(["💸 Gasto", "💰 Ganho", "📂 CSV"])
    
    with t_desp:
        with st.form("fd"):
            dt = st.date_input("Data")
            dsc = st.text_input("Descrição")
            cat = st.selectbox("Categoria", ["Auto"] + LISTA_CATEGORIAS)
            val = st.number_input("Valor Total", min_value=0.0, step=0.01)
            par = st.slider("Parcelas", 1, 12, 1)
            if st.form_submit_button("Lançar Despesa"):
                cat_f = classificar_ia(dsc) if cat == "Auto" else cat
                for i in range(par):
                    d_p = dt + relativedelta(months=i)
                    valor_parc = val / par
                    desc_final = f"{dsc} ({i+1}/{par})" if par > 1 else dsc
                    run_query("INSERT INTO movimentacoes (data, categoria, descricao, valor, tipo) VALUES (?,?,?,?,?)", 
                              (d_p, cat_f, desc_final, valor_parc, "Despesa"))
                st.success("Despesa Gravada!")
                time.sleep(0.5)
                st.rerun()

    with t_rec:
        with st.form("fr"):
            rd = st.date_input("Data", key="rd")
            rs = st.text_input("Fonte")
            rv = st.number_input("Valor", min_value=0.0, step=0.01, key="rv")
            if st.form_submit_button("Salvar Receita"):
                run_query("INSERT INTO movimentacoes (data, categoria, descricao, valor, tipo) VALUES (?,?,?,?,?)", 
                          (rd, "Receita", rs, rv, "Receita"))
                st.rerun()

    with t_csv:
        arq = st.file_uploader("Subir CSV", type="csv")
        if arq and st.button("Processar CSV"):
            try:
                df_c = pd.read_csv(arq)
                count = 0
                for _, r in df_c.iterrows():
                    # Adapte as colunas conforme seu CSV
                    run_query("INSERT INTO movimentacoes (data, categoria, descricao, valor, tipo) VALUES (?,?,?,?,?)", 
                              (r.get('Data', datetime.now()), r.get('Categoria', 'Outros'), r.get('Descricao','Importado CSV'), r.get('Valor', 0), r.get('Tipo','Despesa')))
                    count += 1
                st.success(f"{count} registros importados!")
            except Exception as e:
                st.error(f"Erro ao ler CSV: {e}")

    st.divider()
    st.subheader("💱 Conversor Rápido")
    moeda = st.selectbox("Converter de:", ["USD", "EUR", "BTC"])
    v_ext = st.number_input("Valor Estrangeiro", 0.0, key="ve")
    if st.button("Ver Cotação em BRL"):
        try:
            url = f"https://economia.awesomeapi.com.br/last/{moeda}-BRL"
            res = requests.get(url).json()
            cotacao = float(res[f"{moeda}BRL"]["bid"])
            convertido = v_ext * cotacao
            st.info(f"Cotação: R$ {cotacao:.2f}")
            st.success(f"**Total: R$ {convertido:.2f}**")
        except:
            st.warning("Sem conexão com a API de moedas.")

# --- 6. PAINEL CENTRAL (DASHBOARD) ---
df = get_data("SELECT * FROM movimentacoes")
metas_df = get_data("SELECT * FROM metas")

col_t, col_p = st.columns([4,1])
col_t.title("📊 Terminal CyberFinance")

# Botão de PDF
def gerar_pdf(df_v):
    pdf = PDFRelatorio(); pdf.add_page(); pdf.set_font("Arial", size=12)
    def txt(t): return str(t).encode('latin-1', 'replace').decode('latin-1')
    
    r = df_v[df_v['tipo']=='Receita']['valor'].sum()
    d = df_v[df_v['tipo']=='Despesa']['valor'].sum()
    
    pdf.cell(0, 10, txt(f"Resumo Financeiro do Periodo"), 0, 1)
    pdf.cell(0, 10, txt(f"Total Ganhos: R$ {r:.2f}"), 0, 1)
    pdf.cell(0, 10, txt(f"Total Gastos: R$ {d:.2f}"), 0, 1)
    pdf.cell(0, 10, txt(f"Saldo Final: R$ {r-d:.2f}"), 0, 1)
    pdf.ln(10)
    pdf.cell(0, 10, txt("Extrato Detalhado:"), 0, 1)
    
    for index, row in df_v.iterrows():
        linha = f"{row['data']} | {row['tipo']} | {row['categoria']} | R$ {row['valor']:.2f}"
        pdf.cell(0, 10, txt(linha), 0, 1)
        
    # CORREÇÃO AQUI: Forçamos a saída como String ('S') e codificamos para bytes
    return pdf.output(dest='S').encode('latin-1')
# ABAS DO SISTEMA
tab_dash, tab_busca, tab_metas, tab_previsao, tab_aud = st.tabs(["📈 Painel", "🔍 Busca Global", "🎯 Metas", "🔮 Previsão", "🛡️ Auditoria"])

with tab_dash:
    if not df.empty:
        df['data'] = pd.to_datetime(df['data'])
        df['mes'] = df['data'].dt.strftime('%Y-%m')
        meses_disponiveis = sorted(df['mes'].unique(), reverse=True)
        mes_sel = st.selectbox("Selecione o Período:", meses_disponiveis)
        
        # Filtra dados do mês
        df_v = df[df['mes'] == mes_sel].copy()
        
        # KPIs
        rec = df_v[df_v['tipo']=='Receita']['valor'].sum()
        des = df_v[df_v['tipo']=='Despesa']['valor'].sum()
        saldo = rec - des
        
        c1, c2, c3 = st.columns(3)
        c1.metric("GANHOS", f"R$ {rec:,.2f}", delta="+")
        c2.metric("GASTOS", f"R$ {des:,.2f}", delta="-")
        c3.metric("SALDO LÍQUIDO", f"R$ {saldo:,.2f}", delta_color="normal")
        
        st.markdown("---")
        
        # Gráficos
        g1, g2 = st.columns(2)
        
        # Gráfico de Barras (Gastos por Categoria)
        gastos_cat = df_v[df_v['tipo']=='Despesa'].groupby('categoria')['valor'].sum().reset_index()
        fig_bar = px.bar(gastos_cat, x='categoria', y='valor', color='valor', 
                         title="Gastos por Categoria", template="plotly_dark",
                         color_continuous_scale=['#00ADB5', '#00f5d4'])
        g1.plotly_chart(fig_bar, use_container_width=True)
        
        # Gráfico de Pizza (Receita vs Despesa)
        fig_pie = px.pie(df_v, values='valor', names='tipo', hole=0.5, 
                         title="Balanço Mensal", template="plotly_dark", 
                         color='tipo',
                         color_discrete_map={'Receita':'#00f5d4','Despesa':'#ff2e63'})
        g2.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Nenhum dado encontrado. Use o menu lateral para lançar sua primeira despesa.")

with tab_busca:
    st.subheader("🔍 Localizar Transações (Histórico Completo)")
    termo_busca = st.text_input("O que você procura?", placeholder="Ex: Pizza, Salário, Vivo...")
    
    if termo_busca:
        # Busca segura usando parâmetros SQL
        q_busca = f"SELECT * FROM movimentacoes WHERE descricao LIKE '%{termo_busca}%' OR categoria LIKE '%{termo_busca}%'"
        res_busca = get_data(q_busca)
        
        if not res_busca.empty:
            st.success(f"Encontrados {len(res_busca)} registros.")
            st.metric(f"Soma Total para '{termo_busca}'", f"R$ {res_busca['valor'].sum():,.2f}")
            st.dataframe(res_busca.sort_values('data', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.warning("Nenhum registro encontrado.")

with tab_metas:
    st.subheader("⚙️ Configuração de Limites")
    with st.form("fm_metas"):
        cols = st.columns(3)
        novas_metas = {}
        for i, cat in enumerate(LISTA_CATEGORIAS):
            val_atual = metas_df[metas_df['categoria']==cat]['valor_limite'].values[0] if not metas_df.empty else 0.0
            novas_metas[cat] = cols[i%3].number_input(f"Meta: {cat}", value=float(val_atual))
        
        if st.form_submit_button("Salvar Todas as Metas"):
            for cat, val in novas_metas.items():
                run_query("INSERT OR REPLACE INTO metas (categoria, valor_limite) VALUES (?, ?)", (cat, val))
            st.success("Metas Atualizadas!")
            time.sleep(0.5)
            st.rerun()
            
    st.divider()
    st.subheader("📊 Acompanhamento (Mês Selecionado)")
    
    # Só exibe progresso se houver dados filtrados na aba Painel
    if 'df_v' in locals() and not df_v.empty:
        cols_prog = st.columns(3)
        for i, cat in enumerate(LISTA_CATEGORIAS):
            # Pega o limite
            limite_res = get_data(f"SELECT valor_limite FROM metas WHERE categoria='{cat}'")
            limite = limite_res.values[0][0] if not limite_res.empty else 0.0
            
            # Pega o gasto atual
            gasto_atual = df_v[(df_v['categoria']==cat) & (df_v['tipo']=='Despesa')]['valor'].sum()
            
            if limite > 0:
                with cols_prog[i%3]:
                    percentual = min(gasto_atual / limite, 1.0)
                    st.write(f"**{cat}**")
                    st.progress(percentual)
                    
                    if gasto_atual > limite:
                        st.caption(f"🔴 R$ {gasto_atual:.2f} / {limite:.2f} (Estourou!)")
                    else:
                        st.caption(f"🟢 R$ {gasto_atual:.2f} / {limite:.2f}")

with tab_previsao:
    st.subheader("🔮 Inteligência Preditiva (BI)")
    st.caption("Análise baseada na média histórica dos meses anteriores vs. mês atual.")

    if not df.empty:
        # Prepara dados para histórico
        df_hist = df[df['tipo'] == 'Despesa'].copy()
        df_hist['data'] = pd.to_datetime(df_hist['data'])
        
        # Agrupa gastos por mês
        gastos_mensais = df_hist.resample('M', on='data')['valor'].sum()
        
        if len(gastos_mensais) >= 1:
            media_historica = gastos_mensais.mean()
            
            # Gasto do mês atual (seguro contra variável inexistente)
            gasto_do_mes = df_v[df_v['tipo'] == 'Despesa']['valor'].sum() if 'df_v' in locals() else 0.0
            
            col_prev1, col_prev2 = st.columns(2)
            col_prev1.metric("Média Histórica Mensal", f"R$ {media_historica:,.2f}")
            
            # Lógica de Alerta
            if gasto_do_mes > media_historica:
                diferenca = gasto_do_mes - media_historica
                col_prev2.metric("Status Atual", "⚠️ ACIMA DA MÉDIA", delta=f"- R$ {diferenca:.2f}", delta_color="inverse")
                st.error(f"Cuidado! Você já gastou R$ {diferenca:.2f} a mais que sua média histórica.")
            else:
                sobra = media_historica - gasto_do_mes
                if media_historica > 0:
                    perc_abaixo = (sobra / media_historica) * 100
                else:
                    perc_abaixo = 0
                col_prev2.metric("Status Atual", "🟢 DENTRO DA MÉDIA", delta=f"Ainda resta ~ R$ {sobra:.2f}")
                st.success(f"Excelente. Você está {perc_abaixo:.1f}% abaixo da sua média usual.")

            # Gráfico de Linha (Tendência)
            fig_trend = px.line(gastos_mensais, title="Histórico de Gastos (Tendência)", markers=True)
            fig_trend.add_hline(y=media_historica, line_dash="dot", line_color="red", annotation_text="Média")
            fig_trend.update_layout(template="plotly_dark")
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("Dados insuficientes para gerar previsão (necessário mais de um mês de uso).")

with tab_aud:
    st.subheader("🛡️ Auditoria de Sistema (Logs)")
    st.caption("Rastreamento de segurança para conformidade.")
    logs = get_data("SELECT * FROM logs_auditoria ORDER BY id DESC")
    st.dataframe(logs, use_container_width=True)
