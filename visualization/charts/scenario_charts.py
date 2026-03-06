"""
Scenario comparison charts
"""
import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict


class ScenarioComparisonCharts:
    """Charts for comparing different scenarios"""
    
    @staticmethod
    def create_kpi_comparison(scenarios_kpis: List[Dict]) -> go.Figure:
        """
        Compare KPIs across scenarios
        
        Args:
            scenarios_kpis: List of dicts with scenario_name and KPIs
        
        Returns:
            Plotly figure
        """
        df = pd.DataFrame(scenarios_kpis)
        
        fig = go.Figure()
        
        metrics = ['total_cost', 'total_backorder', 'total_overstock', 'total_shortage']
        colors = ['blue', 'red', 'orange', 'purple']
        
        for metric, color in zip(metrics, colors):
            if metric in df.columns:
                fig.add_trace(go.Bar(
                    x=df['scenario_name'],
                    y=df[metric],
                    name=metric.replace('_', ' ').title(),
                    marker_color=color
                ))
        
        fig.update_layout(
            title='Scenario KPI Comparison',
            xaxis_title='Scenario',
            yaxis_title='Value',
            barmode='group',
            template='plotly_white'
        )
        
        return fig
    
    @staticmethod
    def create_service_level_comparison(scenarios_kpis: List[Dict]) -> go.Figure:
        """
        Compare service levels across scenarios
        
        Args:
            scenarios_kpis: List of scenario KPIs
        
        Returns:
            Plotly figure
        """
        df = pd.DataFrame(scenarios_kpis)
        
        fig = go.Figure(data=[
            go.Bar(
                x=df['scenario_name'],
                y=df['service_level'],
                marker_color='lightgreen',
                text=df['service_level'].round(2),
                textposition='auto'
            )
        ])
        
        fig.update_layout(
            title='Service Level Comparison',
            xaxis_title='Scenario',
            yaxis_title='Service Level (%)',
            yaxis_range=[0, 100],
            template='plotly_white'
        )
        
        return fig
