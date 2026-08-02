# Estimativa CLI

Software local em Python para cadastrar propostas comerciais pelo terminal e exportar um PDF inspirado na planilha Debase fornecida. Os cálculos de material, mão de obra, subtotais e total geral são automáticos. Cada proposta também fica salva em JSON para edição futura.

## Instalação

No terminal, dentro desta pasta:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Uso

Criar uma proposta interativamente:

```bash
python3 orcamento.py novo propostas/cliente-obra.json
```

O editor mostra um menu para cadastrar itens, condições comerciais e responsabilidades. Nas descrições com várias linhas, digite um ponto (`.`) sozinho para finalizar.

Reabrir uma proposta:

```bash
python3 orcamento.py editar propostas/cliente-obra.json
```

Gerar ou regenerar o PDF:

```bash
python3 orcamento.py pdf propostas/cliente-obra.json
```

Mostrar os totais sem editar:

```bash
python3 orcamento.py mostrar propostas/cliente-obra.json
```

Criar arquivos de demonstração:

```bash
python3 orcamento.py exemplo
```

O exemplo é gravado em `output/proposta-exemplo.json` e `output/proposta-exemplo.pdf`.

## Valores

O programa aceita valores no formato brasileiro (`20.000,50`) ou decimal simples (`20000.50`). O PDF sempre mostra valores em reais no formato brasileiro.

## Testes

```bash
python3 -m unittest discover -s tests
```
