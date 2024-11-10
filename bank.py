import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
import re

class TransactionAnalyzer:
    def __init__(self, df):
        self.df = df.copy()
        self.prepare_data()
        
    def prepare_data(self):
        """Prepare data for analysis"""
        # Convert Transaction Date to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(self.df['Transaction Date']):
            try:
                self.df['Transaction Date'] = pd.to_datetime(
                    self.df['Transaction Date'],
                    format='mixed',
                    dayfirst=True  # Assuming DD-MM-YYYY format
                )
            except Exception as e:
                st.error(f"Error converting dates: {str(e)}")
                st.write("Sample date from data:", self.df['Transaction Date'].iloc[0])
                return

        # Convert amounts to numeric
        self.df['Debit Amount'] = pd.to_numeric(self.df['Debit Amount'], errors='coerce').fillna(0)
        self.df['Credit Amount'] = pd.to_numeric(self.df['Credit Amount'], errors='coerce').fillna(0)
        self.df['Line Balance'] = pd.to_numeric(self.df['Line Balance'], errors='coerce').fillna(0)
        
        # Create transaction amount (positive for credits, negative for debits)
        self.df['Transaction Amount'] = self.df['Credit Amount'] - self.df['Debit Amount']
        
        # Add date components for analysis
        self.df['MonthYear'] = self.df['Transaction Date'].dt.strftime('%Y-%m')
        
        # Extract patterns from narration
        self.df['Transaction Type'] = self.df['Narration'].apply(self.extract_transaction_type)

    def extract_transaction_type(self, narration):
        """Extract transaction type from narration"""
        narration = str(narration).upper()
        if 'NEFT' in narration:
            return 'NEFT'
        elif 'IMPS' in narration:
            return 'IMPS'
        elif 'UPI' in narration:
            return 'UPI'
        elif 'ATM' in narration:
            return 'ATM'
        elif 'TRANSFER' in narration:
            return 'TRANSFER'
        else:
            return 'OTHER'

    def detect_anomalies(self):
        """Detect anomalous transactions using Isolation Forest"""
        features = ['Transaction Amount', 'Line Balance']
        X = self.df[features]
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        clf = IsolationForest(contamination=0.1, random_state=42)
        self.df['Is_Anomaly'] = clf.fit_predict(X_scaled)
        
        return self.df[self.df['Is_Anomaly'] == -1]

    def find_structured_transactions(self, tolerance=0.01):
        """Detect potentially structured transactions"""
        structured = []
        amounts = self.df['Debit Amount'].unique()
        
        for amount in amounts:
            if amount > 0:
                similar_transactions = self.df[
                    abs(self.df['Debit Amount'] - amount) <= amount * tolerance
                ]
                if len(similar_transactions) >= 3:  # At least 3 similar transactions
                    structured.append({
                        'Amount': amount,
                        'Count': len(similar_transactions),
                        'Date_Range': f"{similar_transactions['Transaction Date'].min().strftime('%Y-%m-%d')} to "
                                    f"{similar_transactions['Transaction Date'].max().strftime('%Y-%m-%d')}",
                        'Total_Value': similar_transactions['Debit Amount'].sum()
                    })
        
        return pd.DataFrame(structured)

def create_dashboard():
    st.set_page_config(
        page_title="Bank Statement Investigation Dashboard", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🔍 Bank Statement Investigation Dashboard")
    
    uploaded_file = st.file_uploader("Upload Bank Statement (Excel format)", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        try:
            # Load data
            df = pd.read_excel(uploaded_file)
            
            # Initialize analyzer
            analyzer = TransactionAnalyzer(df)
            
            # Sidebar filters
            st.sidebar.header("Filters")
            
            # Date range filter
            min_date = analyzer.df['Transaction Date'].min()
            max_date = analyzer.df['Transaction Date'].max()
            date_range = st.sidebar.date_input(
                "Select Date Range",
                [min_date, max_date],
                min_value=min_date,
                max_value=max_date
            )
            
            # Apply filters
            mask = (analyzer.df['Transaction Date'].dt.date >= date_range[0]) & \
                  (analyzer.df['Transaction Date'].dt.date <= date_range[1])
            filtered_df = analyzer.df[mask]
            
            # Main dashboard
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Total Transactions",
                    f"{len(filtered_df):,}"
                )
            
            with col2:
                st.metric(
                    "Total Credits",
                    f"₹{filtered_df['Credit Amount'].sum():,.2f}"
                )
            
            with col3:
                st.metric(
                    "Total Debits",
                    f"₹{filtered_df['Debit Amount'].sum():,.2f}"
                )
            
            with col4:
                st.metric(
                    "Net Balance",
                    f"₹{filtered_df['Line Balance'].iloc[-1]:,.2f}"
                )

            # Transaction Analysis
            st.header("Transaction Analysis")
            
            tab1, tab2, tab3 = st.tabs(["Time Analysis", "Pattern Detection", "Anomalies"])
            
            with tab1:
                # Monthly transaction trend
                monthly_data = filtered_df.groupby('MonthYear').agg({
                    'Credit Amount': 'sum',
                    'Debit Amount': 'sum',
                    'Transaction Date': 'count'
                }).reset_index()
                
                fig_monthly = go.Figure()
                fig_monthly.add_trace(go.Bar(
                    x=monthly_data['MonthYear'],
                    y=monthly_data['Credit Amount'],
                    name='Credits',
                    marker_color='green'
                ))
                fig_monthly.add_trace(go.Bar(
                    x=monthly_data['MonthYear'],
                    y=monthly_data['Debit Amount'],
                    name='Debits',
                    marker_color='red'
                ))
                fig_monthly.update_layout(
                    title='Monthly Transaction Volume',
                    barmode='group'
                )
                st.plotly_chart(fig_monthly, use_container_width=True)
                
                # Balance trend
                fig_balance = px.line(
                    filtered_df,
                    x='Transaction Date',
                    y='Line Balance',
                    title='Balance Trend'
                )
                st.plotly_chart(fig_balance, use_container_width=True)
            
            with tab2:
                # Transaction type distribution
                st.subheader("Transaction Types")
                type_data = filtered_df['Transaction Type'].value_counts()
                fig_types = px.pie(
                    values=type_data.values,
                    names=type_data.index,
                    title='Transaction Type Distribution'
                )
                st.plotly_chart(fig_types, use_container_width=True)
                
                # Structured transactions
                st.subheader("Structured Transactions")
                structured = analyzer.find_structured_transactions()
                if not structured.empty:
                    st.dataframe(structured)
                else:
                    st.write("No structured transactions detected")
            
            with tab3:
                # Anomaly detection
                st.subheader("Transaction Anomalies")
                anomalies = analyzer.detect_anomalies()
                if not anomalies.empty:
                    st.dataframe(
                        anomalies[[
                            'Transaction Date', 'Narration',
                            'Debit Amount', 'Credit Amount',
                            'Line Balance'
                        ]]
                    )
                
                    # Visualize anomalies
                    fig_anomalies = px.scatter(
                        analyzer.df,
                        x='Transaction Date',
                        y='Transaction Amount',
                        color='Is_Anomaly',
                        title='Transaction Anomalies'
                    )
                    st.plotly_chart(fig_anomalies, use_container_width=True)
                else:
                    st.write("No anomalies detected")
            
            # Transaction Details
            st.header("Transaction Details")
            n_rows = st.slider("Number of transactions to display", 5, 50, 10)
            st.dataframe(
                filtered_df[[
                    'Transaction Date', 'Narration',
                    'Debit Amount', 'Credit Amount',
                    'Line Balance', 'Transaction Type'
                ]]
                .sort_values('Transaction Date', ascending=False)
                .head(n_rows)
            )
            
            # Download options
            st.sidebar.header("Download Analysis")
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.sidebar.download_button(
                "Download Full Analysis",
                csv,
                "bank_statement_analysis.csv",
                "text/csv",
                key='download-full'
            )
            
            if not anomalies.empty:
                csv_anomalies = anomalies.to_csv(index=False).encode('utf-8')
                st.sidebar.download_button(
                    "Download Anomalies",
                    csv_anomalies,
                    "anomalies.csv",
                    "text/csv",
                    key='download-anomalies'
                )
            
        except Exception as e:
            st.error(f"Error processing the file: {str(e)}")
            st.write("Please ensure your Excel file has these columns:")
            st.write("- Transaction Date")
            st.write("- Narration")
            st.write("- Debit Amount")
            st.write("- Credit Amount")
            st.write("- Line Balance")

if __name__ == "__main__":
    create_dashboard()