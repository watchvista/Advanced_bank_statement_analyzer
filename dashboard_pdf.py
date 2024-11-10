import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re

def extract_account_from_narration(narration):
    """Extract account numbers or beneficiary details from narration"""
    # This is a simple example - modify based on your narration format
    account_patterns = re.findall(r'\b\d{10,12}\b', str(narration))  # Looking for 10-12 digit numbers
    return account_patterns[0] if account_patterns else narration[:20]

def analyze_transaction_patterns(df):
    """Analyze transaction patterns for investigation"""
    # Frequent transaction partners
    df['Beneficiary'] = df['Narration'].apply(extract_account_from_narration)
    frequent_partners = df.groupby('Beneficiary').agg({
        'Transaction Date': 'count',
        'Debit Amount': 'sum',
        'Credit Amount': 'sum'
    }).sort_values('Transaction Date', ascending=False).reset_index()
    frequent_partners.columns = ['Beneficiary', 'Transaction Count', 'Total Debits', 'Total Credits']
    
    # Round trip transactions (money going out and coming back)
    df['Transaction Month'] = df['Transaction Date'].dt.to_period('M')
    round_trips = []
    
    return frequent_partners, round_trips

def load_and_preprocess_data(file):
    """Load and preprocess the bank statement data"""
    # Read the Excel file
    df = pd.read_excel(file)
    
    # Split Branch Name/IFSC Code into separate columns
    df[['Branch Name', 'IFSC Code']] = df['Branch Name/ IFSC Code'].str.split(' - ', expand=True)
    
    # Convert Transaction Date to datetime
    df['Transaction Date'] = pd.to_datetime(df['Transaction Date'])
    
    # Extract time components
    df['Date'] = df['Transaction Date'].dt.date
    df['Time'] = df['Transaction Date'].dt.time
    df['Year'] = df['Transaction Date'].dt.year
    df['Month'] = df['Transaction Date'].dt.month
    df['Month_Year'] = df['Transaction Date'].dt.strftime('%Y-%m')
    
    # Convert amount columns to numeric
    df['Debit Amount'] = pd.to_numeric(df['Debit Amount'], errors='coerce').fillna(0)
    df['Credit Amount'] = pd.to_numeric(df['Credit Amount'], errors='coerce').fillna(0)
    df['Line Balance'] = pd.to_numeric(df['Line Balance'], errors='coerce').fillna(0)
    
    return df

def create_dashboard():
    st.set_page_config(page_title="Bank Statement Investigation Dashboard", 
                      layout="wide",
                      initial_sidebar_state="expanded")
    
    st.title("🔍 Bank Statement Investigation Dashboard")
    
    uploaded_file = st.file_uploader("Upload Bank Statement (Excel format)", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        try:
            df = load_and_preprocess_data(uploaded_file)
            
            # Sidebar filters
            st.sidebar.header("Filters")
            
            # Date range filter
            date_range = st.sidebar.date_input(
                "Select Date Range",
                [df['Date'].min(), df['Date'].max()]
            )
            
            # Amount range filter
            max_amount = max(df['Debit Amount'].max(), df['Credit Amount'].max())
            amount_range = st.sidebar.slider(
                "Transaction Amount Range",
                0.0,
                float(max_amount),
                (0.0, float(max_amount))
            )
            
            # Apply filters
            filtered_df = df[
                (df['Date'] >= date_range[0]) &
                (df['Date'] <= date_range[1]) &
                ((df['Debit Amount'].between(amount_range[0], amount_range[1])) |
                 (df['Credit Amount'].between(amount_range[0], amount_range[1])))
            ]
            
            # Key Metrics
            st.header("Key Metrics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Credits", f"₹{filtered_df['Credit Amount'].sum():,.2f}")
            with col2:
                st.metric("Total Debits", f"₹{filtered_df['Debit Amount'].sum():,.2f}")
            with col3:
                st.metric("Net Balance", f"₹{filtered_df['Line Balance'].iloc[-1]:,.2f}")
            with col4:
                st.metric("Total Transactions", len(filtered_df))
            
            # Transaction Analysis
            st.header("Transaction Analysis")
            
            # Most Active Month/Year Analysis
            monthly_trans = filtered_df.groupby('Month_Year').agg({
                'Transaction Date': 'count',
                'Debit Amount': 'sum',
                'Credit Amount': 'sum'
            }).reset_index()
            
            most_active_month = monthly_trans.loc[monthly_trans['Transaction Date'].idxmax()]
            
            st.subheader("Most Active Period")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Most Active Month", 
                         most_active_month['Month_Year'],
                         f"{most_active_month['Transaction Date']} transactions")
            
            # Transaction Pattern Analysis
            st.subheader("Transaction Patterns")
            tab1, tab2 = st.tabs(["Monthly Patterns", "Transaction Partners"])
            
            with tab1:
                # Monthly transaction volume
                fig_monthly = px.bar(
                    monthly_trans,
                    x='Month_Year',
                    y='Transaction Date',
                    title='Monthly Transaction Volume'
                )
                st.plotly_chart(fig_monthly, use_container_width=True)
            
            with tab2:
                # Most frequent transaction partners
                frequent_partners, _ = analyze_transaction_patterns(filtered_df)
                st.write("Most Frequent Transaction Partners")
                st.dataframe(
                    frequent_partners.head(10),
                    use_container_width=True
                )
            
            # Suspicious Pattern Detection
            st.header("Investigation Insights")
            
            # Large Transactions
            large_transactions = filtered_df[
                (filtered_df['Debit Amount'] > filtered_df['Debit Amount'].quantile(0.95)) |
                (filtered_df['Credit Amount'] > filtered_df['Credit Amount'].quantile(0.95))
            ]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Large Transactions")
                st.dataframe(
                    large_transactions[['Transaction Date', 'Narration', 'Debit Amount', 'Credit Amount']]
                    .sort_values('Transaction Date', ascending=False),
                    use_container_width=True
                )
            
            with col2:
                # Transaction timing patterns
                st.subheader("Transaction Timing Patterns")
                filtered_df['Hour'] = filtered_df['Time'].apply(lambda x: x.hour)
                hourly_pattern = filtered_df.groupby('Hour').size().reset_index(name='count')
                fig_timing = px.line(hourly_pattern, x='Hour', y='count', 
                                   title='Transaction Timing Distribution')
                st.plotly_chart(fig_timing, use_container_width=True)
            
            # Additional Investigation Features
            st.header("Detailed Analysis")
            
            # Round-trip transactions
            st.subheader("Potential Round-trip Transactions")
            similar_amounts = filtered_df[
                filtered_df.duplicated(subset=['Debit Amount'], keep=False) |
                filtered_df.duplicated(subset=['Credit Amount'], keep=False)
            ].sort_values('Transaction Date')
            
            st.dataframe(
                similar_amounts[['Transaction Date', 'Narration', 'Debit Amount', 'Credit Amount', 'Line Balance']],
                use_container_width=True
            )
            
            # Download filtered data
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Analysis Data",
                csv,
                "bank_statement_analysis.csv",
                "text/csv",
                key='download-csv'
            )
            
        except Exception as e:
            st.error(f"Error processing the file: {str(e)}")
            st.write("Please ensure your Excel file has the following columns:")
            st.write("- Branch Name/ IFSC Code")
            st.write("- Transaction ID")
            st.write("- Transaction Date")
            st.write("- Narration")
            st.write("- Debit Amount")
            st.write("- Credit Amount")
            st.write("- Line Balance")

if __name__ == "__main__":
    create_dashboard()