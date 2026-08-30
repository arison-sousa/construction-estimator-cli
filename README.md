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

Abrir a tela inicial:

```bash
python3 orcamento.py
```

A tela permite criar uma proposta, selecionar uma proposta salva para editar ou revisar, listar propostas, visualizar o PDF e abrir a pasta de propostas no Finder.

Criar uma proposta interativamente:

```bash
python3 orcamento.py novo
```

O programa atribui automaticamente o próximo número disponível no ano atual e cria um nome legível e compatível com Windows e macOS:

```text
0001-26-00 - JBS Ipumirim - Reforma Piso Almoxarifado.json
```

Por padrão, as propostas são salvas fora do repositório do programa em `~/Documents/debase-proposals`. A pasta é criada automaticamente na primeira proposta, para que PDFs, JSON e planilhas não façam parte do código-fonte ou de uma release.

Para salvar em outra pasta, use `--diretorio`:

```bash
python3 orcamento.py novo --diretorio "/caminho/para/minhas-propostas"
```

O editor permite adicionar seções (sempre acompanhadas do primeiro item), acrescentar itens a uma seção e editar as condições comerciais. Ao adicionar um item, informe o número da seção ou pressione `Enter` para usar a última. Para editar ou remover uma linha, informe o número da seção ou do item, como `2` ou `2.1`. Editar uma seção altera seu título; editar um item permite atualizar sua descrição, unidade, quantidade e valores. As responsabilidades permanecem com o texto padrão da proposta.

Ao preencher uma descrição com várias linhas, o programa abre um editor de texto onde é possível colar, navegar e corrigir todo o conteúdo. Use as setas para navegar, `Ctrl+O` e `Enter` para salvar e `Ctrl+X` para voltar à proposta.

Reabrir uma proposta:

```bash
python3 orcamento.py editar propostas/cliente-obra.json
```

Editar mantém o número e a revisão atuais. Para preservar a proposta original e criar a próxima revisão:

```bash
python3 orcamento.py revisar "propostas/0001-26-00 - JBS Ipumirim - Reforma Piso Almoxarifado.json"
```

Esse comando cria a revisão `01`; revisões posteriores avançam para `02`, `03` e assim por diante.

Gerar ou regenerar o PDF:

```bash
python3 orcamento.py pdf propostas/cliente-obra.json
```

Gerar uma planilha Excel editável e formatada para impressão:

```bash
python3 orcamento.py excel propostas/cliente-obra.json
```

O Excel mantém o visual da proposta, inclui fórmulas para os totais de material e mão de obra e é salvo ao lado do JSON com a extensão `.xlsx`. Para escolher outro destino, use `-o arquivo.xlsx`.

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
