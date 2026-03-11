# GideonOS

Este repositório contém o código do projeto GideonOS.

## 🛠️ Como instalar em outro computador

Siga o passo a passo abaixo para rodar este projeto em uma nova máquina após clonar o repositório.

### 1. Clonar o repositório
Abra o terminal na pasta em que deseja baixar o projeto e rode:
```bash
git clone https://github.com/douglasrodolfolfo/GideonOS.git
cd GideonOS
```

### 2. Criar e ativar o Ambiente Virtual (Venv)
O Python utiliza ambientes virtuais para não misturar as bibliotecas deste projeto com as do computador.
```bash
# Cria o ambiente virtual na pasta .venv
python -m venv .venv

# Ativa o ambiente virtual (Windows)
.\.venv\Scripts\activate

# Ativa o ambiente virtual (Mac/Linux)
# source .venv/bin/activate
```

### 3. Instalar as Dependências
Com o ambiente virtual ativado (você verá um `(.venv)` no início do seu terminal), instale todas as bibliotecas necessárias:
```bash
pip install -r requirements.txt
```

### 4. Configurar as Variáveis de Ambiente
O projeto precisa de tokens e chaves que não são salvos publicamente no GitHub por segurança.
1. Na pasta principal do projeto, faça uma cópia do arquivo `.env.example` e renomeie-o para `.env`.
2. Abra o arquivo `.env` e preencha as informações necessárias com os seus dados reais (como o `TELEGRAM_TOKEN`).

### 5. Executar o projeto
Agora você já está pronto para rodar os arquivos principais. Exemplo:
```bash
python pump_detector.py
```
