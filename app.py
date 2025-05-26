from flask import Flask, render_template, request, redirect, session, url_for
import pyodbc
import os

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'chave-padrao-fraca')

def conectar_banco():
    try:
        connection_string = os.getenv('DATABASE_URL')
        conexao = pyodbc.connect(connection_string)
        return conexao
    except Exception as e:
        print("Erro ao conectar:", e)
        return None

@app.route('/', methods=['GET', 'POST'])
def login():
    mensagem = ''
    if request.method == 'POST':
        id_motorista = request.form['id_motorista']
        senha = request.form['cpf']

        conexao = conectar_banco()
        if conexao:
            cursor = conexao.cursor()
            cursor.execute("SELECT * FROM Motoristas WHERE ID_Motorista = ? AND CPF = ?", (id_motorista, senha))
            motorista = cursor.fetchone()
            cursor.close()
            conexao.close()

            if motorista:
                session['id_motorista'] = id_motorista
                return redirect(url_for('painel'))
            else:
                mensagem = 'ID ou Senha incorretos.'

    return render_template('login.html', mensagem=mensagem)

def calcular_media(lista, chave, ignora_percentual=False):
    valores = []
    for item in lista:
        valor = item[chave]
        if not valor or valor == "-":
            continue
        if ignora_percentual:
            valor = str(valor).replace("%", "").strip().replace(",", ".")
        try:
            valor_float = float(valor)
            valores.append(valor_float)
        except ValueError:
            continue
    if not valores:
        return "-"
    media = sum(valores) / len(valores)
    return round(media, 2)


@app.route('/painel')
def painel():
    if 'id_motorista' not in session:
        return redirect(url_for('login'))

    id_motorista = session['id_motorista']
    conexao = conectar_banco()
    dados_formatados = []
    observacoes = []

    if conexao:
        cursor = conexao.cursor()
        try:
            # Buscar indicadores
            cursor.execute("""
                SELECT 
                    CONVERT(varchar, D.Data, 23) AS DataISO, 
                    D.Devolucao_Porcentagem, 
                    S.Dispersao_KM,
                    R.Rating,
                    P.Reposicao_Valor,
                    F.Refugo_Porcentagem
                FROM Devolucao D
                LEFT JOIN Dispersao S ON D.ID_Motorista = S.ID_Motorista AND D.Data = S.Data
                LEFT JOIN Rating R ON D.ID_Motorista = R.ID_Motorista AND D.Data = R.Data
                LEFT JOIN Reposicao P ON D.ID_Motorista = P.ID_Motorista AND D.Data = P.Data
                LEFT JOIN Refugo F ON D.ID_Motorista = F.ID_Motorista AND D.Data = F.Data
                WHERE D.ID_Motorista = ?
                ORDER BY D.Data ASC
            """, (id_motorista,))
            
            resultados = cursor.fetchall()

            for linha in resultados:
                data = linha.DataISO
                if data:
                    partes = data.split('-')
                    data_formatada = f"{partes[2]}-{partes[1]}-{partes[0]}"
                else:
                    data_formatada = "-"

                # Remove % da devolução porcentagem para cálculo e exibição consistentes
                devolucao_porcentagem_valor = linha.Devolucao_Porcentagem
                if devolucao_porcentagem_valor is not None:
                    devolucao_porcentagem_valor = str(devolucao_porcentagem_valor).replace("%", "").strip()
                else:
                    devolucao_porcentagem_valor = "-"

                dados_formatados.append({
                    'Data': data_formatada,
                    'Devolucao_Porcentagem': devolucao_porcentagem_valor,
                    'Dispersao_KM': linha.Dispersao_KM if linha.Dispersao_KM is not None else "-",
                    'Rating': linha.Rating if linha.Rating is not None else "-",
                    'Reposicao_Valor': linha.Reposicao_Valor if linha.Reposicao_Valor is not None else "-",
                    'Refugo_Porcentagem': linha.Refugo_Porcentagem if linha.Refugo_Porcentagem is not None else "-"
                })


            # Buscar observações
            cursor.execute("SELECT Texto FROM Observacoes WHERE ID_Motorista = ?", (id_motorista,))
            observacoes = [linha.Texto for linha in cursor.fetchall()]

        except Exception as e:
            print("Erro ao consultar o banco:", e)
        finally:
            cursor.close()
            conexao.close()

    media_devolucao_porcentagem = calcular_media(dados_formatados, 'Devolucao_Porcentagem', ignora_percentual=True)
    media_dispersao_km = calcular_media(dados_formatados, 'Dispersao_KM', ignora_percentual=True)
    media_rating = calcular_media(dados_formatados, 'Rating')
    media_reposicao = calcular_media(dados_formatados, 'Reposicao_Valor', ignora_percentual=True)
    media_refugo = calcular_media(dados_formatados, 'Refugo_Porcentagem', ignora_percentual=True)



    return render_template('painel.html', dados=dados_formatados, observacoes=observacoes,
                       medias={
                           'Devolucao_Porcentagem': media_devolucao_porcentagem,
                           'Dispersao_KM': media_dispersao_km,
                           'Rating': media_rating,
                           'Reposicao_Valor': media_reposicao,
                           'Refugo_Porcentagem': media_refugo
})

@app.route('/explicacoes')
def explicacoes():
    if 'id_motorista' not in session:
        return redirect(url_for('login'))
    return render_template('explicacoes.html')

@app.route('/observacao', methods=['POST'])
def observacao():
    if 'id_motorista' not in session:
        return redirect(url_for('login'))

    texto = request.form.get('observacao', '').strip()
    id_motorista = session['id_motorista']

    if texto:
        conexao = conectar_banco()
        if conexao:
            cursor = conexao.cursor()
            try:
                cursor.execute("INSERT INTO Observacoes (ID_Motorista, Texto) VALUES (?, ?)", (id_motorista, texto))
                conexao.commit()
            except Exception as e:
                print("Erro ao salvar observação:", e)
            finally:
                cursor.close()
                conexao.close()

    return redirect(url_for('painel'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
