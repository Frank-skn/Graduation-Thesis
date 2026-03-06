"""
Sensitivity analysis visualization
"""
import plotly.graph_objects as go
import numpy as np
from typing import List, Dict


class SensitivityCharts:
    """Charts for sensitivity analysis"""
    
    @staticmethod
    def create_parameter_sensitivity(
        parameter_name: str,
        values: List[float],
        objectives: List[float]
    ) -> go.Figure:
        """
        Show how objective changes with parameter
        
        Args:
            parameter_name: Name of parameter being varied
            values: Parameter values
            objectives: Corresponding objective values
        
        Returns:
            Plotly figure
        """
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=values,
            y=objectives,
            mode='lines+markers',
            name='Objective Value',
            line=dict(color='blue', width=2),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title=f'Sensitivity Analysis: {parameter_name}',
            xaxis_title=parameter_name,
            yaxis_title='Total Cost',
            template='plotly_white',
            hovermode='x unified'
        )
        
        return fig
    
    @staticmethod
    def create_multi_parameter_sensitivity(
        sensitivity_data: Dict[str, List[Dict]]
    ) -> go.Figure:
        """
        Compare sensitivity across multiple parameters
        
        Args:
            sensitivity_data: Dict mapping parameter names to results
        
        Returns:
            Plotly figure
        """
        fig = go.Figure()
        
        for param_name, data in sensitivity_data.items():
            values = [d['value'] for d in data]
            objectives = [d['objective'] for d in data]
            
            fig.add_trace(go.Scatter(
                x=values,
                y=objectives,
                mode='lines+markers',
                name=param_name,
                line=dict(width=2),
                marker=dict(size=6)
            ))
        
        fig.update_layout(
            title='Multi-Parameter Sensitivity Analysis',
            xaxis_title='Parameter Value (Normalized)',
            yaxis_title='Total Cost',
            template='plotly_white',
            hovermode='x unified',
            legend=dict(orientation='v', x=1.05, y=1)
        )
        
        return fig
