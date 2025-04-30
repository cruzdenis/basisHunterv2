# BasisHunter - Delta Zero Arbitragem de Funding Rate

Este app executa e monitora operações de arbitragem delta-neutra entre contratos perpétuos e futuros trimestrais na Binance.

## 📦 Instalação

```bash
pip install -r requirements.txt
```

## 🚀 Como Rodar

```bash
streamlit run app.py
```

## ⚙️ Configuração

Crie um arquivo `.env` com suas chaves da Binance:

```
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
```

## 📁 Estrutura

- `app.py` — Interface principal do Streamlit
- `operacoes_reais.json` — Histórico local das operações
- `.env` — Suas credenciais privadas (NÃO FAZER COMMIT)
