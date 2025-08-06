import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

def process_precipitation_data(file_path):
    """
    Processa dados de precipitação diária a partir de um arquivo CSV.
    
    Args:
        file_path (str): Caminho para o arquivo CSV
        
    Returns:
        tuple: (DataFrame com dados diários, DataFrame com dados mensais)
    """
    # 1. Leitura dos dados
    try:
        # Ler o arquivo CSV com tratamento para o cabeçalho e formato decimal
        df = pd.read_csv(
            file_path,
            sep=';',
            decimal=',',
            parse_dates=['data'],
            dayfirst=True,
            encoding='utf-8'
        )
        
        # Renomear coluna para padrão consistente
        df.columns = ['data', 'precipitacao_mm']
        
    except Exception as e:
        print(f"Erro ao ler o arquivo: {e}")
        return None, None
    
    # 2. Limpeza e validação dos dados
    # Converter precipitação para float (tratando vírgulas como decimais)
    df['precipitacao_mm'] = df['precipitacao_mm'].astype(str).str.replace(',', '.').astype(float)
    
    # Verificar dados ausentes
    if df['precipitacao_mm'].isnull().sum() > 0:
        print(f"Aviso: {df['precipitacao_mm'].isnull().sum()} valores de precipitação ausentes")
        # Preencher ausentes com 0 (assumindo que ausente = sem precipitação)
        df['precipitacao_mm'] = df['precipitacao_mm'].fillna(0)
    
    # 3. Adicionar colunas auxiliares
    df['ano'] = df['data'].dt.year
    df['mes'] = df['data'].dt.month
    df['dia'] = df['data'].dt.day
    
    # 4. Criar dataframe agregado por mês
    monthly = df.groupby(['ano', 'mes']).agg({
        'precipitacao_mm': ['sum', 'mean', 'max', 'count'],
        'data': ['min', 'max']
    })
    
    # Simplificar colunas multi-index
    monthly.columns = ['total_mensal', 'media_diaria', 'maxima_diaria', 'dias_registrados', 
                      'primeiro_dia', 'ultimo_dia']
    
    monthly.reset_index(inplace=True)
    
    # Calcular dias esperados no mês
    monthly['dias_esperados'] = monthly.apply(
        lambda x: (datetime(x['ano'], x['mes']+1, 1) - datetime(x['ano'], x['mes'], 1)).days 
        if x['mes'] < 12 else 31, axis=1
    )
    
    # Verificar completude dos dados
    monthly['completo'] = monthly['dias_registrados'] == monthly['dias_esperados']
    
    return df, monthly

def plot_precipitation_data(daily_df, monthly_df):
    """
    Gera gráficos para visualização dos dados de precipitação.
    
    Args:
        daily_df (DataFrame): Dados diários
        monthly_df (DataFrame): Dados mensais
    """
    plt.figure(figsize=(15, 10))
    
    # Gráfico 1: Série temporal diária
    plt.subplot(2, 1, 1)
    plt.plot(daily_df['data'], daily_df['precipitacao_mm'], 'b-', alpha=0.5, label='Diário')
    plt.title('Precipitação Diária')
    plt.ylabel('Precipitação (mm)')
    plt.gca().xaxis.set_major_locator(mdates.YearLocator())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Gráfico 2: Série temporal mensal
    plt.subplot(2, 1, 2)
    monthly_df['data_media'] = pd.to_datetime(
        monthly_df['ano'].astype(str) + '-' + monthly_df['mes'].astype(str) + '-15'
    )
    plt.bar(monthly_df['data_media'], monthly_df['total_mensal'], width=20, label='Mensal')
    plt.title('Precipitação Mensal Acumulada')
    plt.ylabel('Precipitação (mm)')
    plt.gca().xaxis.set_major_locator(mdates.YearLocator())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    plt.show()
    
    # Gráfico 3: Boxplot por mês
    plt.figure(figsize=(12, 6))
    daily_df['mes_ano'] = daily_df['data'].dt.to_period('M')
    boxplot_data = daily_df[daily_df['precipitacao_mm'] > 0].groupby('mes_ano')['precipitacao_mm'].sum()
    boxplot_data.index = boxplot_data.index.astype(str)
    boxplot_data.plot(kind='box')
    plt.title('Distribuição da Precipitação Mensal (apenas meses com chuva)')
    plt.ylabel('Precipitação (mm)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

def generate_report(monthly_df):
    """
    Gera um relatório estatístico básico dos dados.
    
    Args:
        monthly_df (DataFrame): Dados mensais
    """
    print("\nRELATÓRIO DE DADOS DE PRECIPITAÇÃO")
    print("="*50)
    
    # Estatísticas básicas
    total_years = monthly_df['ano'].nunique()
    start_year = monthly_df['ano'].min()
    end_year = monthly_df['ano'].max()
    
    print(f"\nPeríodo analisado: {start_year} - {end_year} ({total_years} anos)")
    print(f"Total de meses registrados: {len(monthly_df)}")
    print(f"Meses com dados completos: {monthly_df['completo'].sum()}")
    
    # Análise de completude
    incomplete_months = monthly_df[~monthly_df['completo']]
    if not incomplete_months.empty:
        print("\nMeses com dados incompletos:")
        print(incomplete_months[['ano', 'mes', 'dias_registrados', 'dias_esperados']])
    
    # Estatísticas de precipitação
    print("\nEstatísticas de Precipitação Mensal:")
    print(f"- Máximo mensal: {monthly_df['total_mensal'].max():.1f} mm")
    print(f"- Média mensal: {monthly_df['total_mensal'].mean():.1f} mm")
    print(f"- Mediana mensal: {monthly_df['total_mensal'].median():.1f} mm")
    
    # Top 5 meses mais chuvosos
    top_months = monthly_df.nlargest(5, 'total_mensal')
    print("\nTop 5 meses mais chuvosos:")
    print(top_months[['ano', 'mes', 'total_mensal']])

def main():
    # Configuração do arquivo de entrada
    input_file = 'indice_mm.csv'
    
    # Processar os dados
    daily_data, monthly_data = process_precipitation_data(input_file)
    
    if daily_data is not None and monthly_data is not None:
        # Gerar visualizações
        plot_precipitation_data(daily_data, monthly_data)
        
        # Gerar relatório
        generate_report(monthly_data)
        
        # Exportar dados processados (opcional)
        daily_data.to_csv('dados_diarios_processados.csv', index=False)
        monthly_data.to_csv('dados_mensais_processados.csv', index=False)
        print("\nDados processados exportados para CSV.")
    else:
        print("Não foi possível processar os dados. Verifique o arquivo de entrada.")

if __name__ == "__main__":
    main()
