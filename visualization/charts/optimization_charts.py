"""
Chart generation for optimization results
Separated visualization logic from UI
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import List, Dict, Any, Optional


class OptimizationCharts:
    """
    Chart generator for optimization results
    Implements Single Responsibility - only chart creation
    """
    
    @staticmethod
    def create_inventory_time_series(
        results: List[Dict[str, Any]],
        product_id: Optional[str] = None,
        warehouse_id: Optional[str] = None
    ) -> go.Figure:
        """
        Create inventory time series chart
        
        Args:
            results: List of optimization results
            product_id: Filter by product (optional)
            warehouse_id: Filter by warehouse (optional)
        
        Returns:
            Plotly figure
        """
        df = pd.DataFrame(results)
        
        # Apply filters
        if product_id:
            df = df[df['product_id'] == product_id]
        if warehouse_id:
            df = df[df['warehouse_id'] == warehouse_id]
        
        # Group by time period
        time_series = df.groupby('time_period').agg({
            'net_inventory': 'sum',
            'backorder_qty': 'sum',
            'overstock_qty': 'sum',
            'shortage_qty': 'sum'
        }).reset_index()
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=time_series['time_period'],
            y=time_series['net_inventory'],
            mode='lines+markers',
            name='Net Inventory',
            line=dict(color='blue', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=time_series['time_period'],
            y=time_series['backorder_qty'],
            mode='lines+markers',
            name='Backorder',
            line=dict(color='red', width=2, dash='dash')
        ))
        
        fig.add_trace(go.Scatter(
            x=time_series['time_period'],
            y=time_series['overstock_qty'],
            mode='lines+markers',
            name='Overstock',
            line=dict(color='orange', width=2, dash='dot')
        ))
        
        fig.update_layout(
            title='Inventory Levels Over Time',
            xaxis_title='Time Period',
            yaxis_title='Quantity',
            hovermode='x unified',
            template='plotly_white'
        )
        
        return fig
    
    @staticmethod
    def create_cost_breakdown(kpis: Dict[str, float]) -> go.Figure:
        """
        Create cost breakdown pie chart
        
        Args:
            kpis: KPI dictionary with cost components
        
        Returns:
            Plotly figure
        """
        labels = ['Backorder', 'Overstock', 'Shortage', 'Penalty']
        values = [
            kpis.get('total_backorder', 0),
            kpis.get('total_overstock', 0),
            kpis.get('total_shortage', 0),
            kpis.get('total_penalty', 0)
        ]
        
        colors = ['#EF553B', '#FFA15A', '#AB63FA', '#00CC96']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker=dict(colors=colors),
            textposition='inside',
            textinfo='label+percent'
        )])
        
        fig.update_layout(
            title='Cost Breakdown by Component',
            template='plotly_white'
        )
        
        return fig
    
    @staticmethod
    def create_warehouse_comparison(results: List[Dict[str, Any]]) -> go.Figure:
        """
        Compare metrics across warehouses
        
        Args:
            results: List of optimization results
        
        Returns:
            Plotly figure
        """
        df = pd.DataFrame(results)
        
        warehouse_metrics = df.groupby('warehouse_id').agg({
            'net_inventory': 'mean',
            'backorder_qty': 'sum',
            'overstock_qty': 'sum',
            'shortage_qty': 'sum'
        }).reset_index()
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=warehouse_metrics['warehouse_id'],
            y=warehouse_metrics['backorder_qty'],
            name='Backorder',
            marker_color='red'
        ))
        
        fig.add_trace(go.Bar(
            x=warehouse_metrics['warehouse_id'],
            y=warehouse_metrics['overstock_qty'],
            name='Overstock',
            marker_color='orange'
        ))
        
        fig.add_trace(go.Bar(
            x=warehouse_metrics['warehouse_id'],
            y=warehouse_metrics['shortage_qty'],
            name='Shortage',
            marker_color='purple'
        ))
        
        fig.update_layout(
            title='Warehouse Performance Comparison',
            xaxis_title='Warehouse',
            yaxis_title='Quantity',
            barmode='group',
            template='plotly_white'
        )
        
        return fig
    
    @staticmethod
    def create_product_heatmap(results: List[Dict[str, Any]]) -> go.Figure:
        """
        Create product-warehouse inventory heatmap
        
        Args:
            results: List of optimization results
        
        Returns:
            Plotly figure
        """
        df = pd.DataFrame(results)
        
        # Aggregate by product and warehouse
        pivot = df.groupby(['product_id', 'warehouse_id'])['net_inventory'].mean().reset_index()
        pivot_table = pivot.pivot(index='product_id', columns='warehouse_id', values='net_inventory')
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot_table.values,
            x=pivot_table.columns,
            y=pivot_table.index,
            colorscale='RdYlGn',
            text=pivot_table.values,
            texttemplate='%{text:.0f}',
            textfont={"size": 10}
        ))
        
        fig.update_layout(
            title='Average Inventory by Product and Warehouse',
            xaxis_title='Warehouse',
            yaxis_title='Product',
            template='plotly_white'
        )
        
        return fig
    
    @staticmethod
    def create_capacity_utilization(results: List[Dict[str, Any]], capacity_data: Dict) -> go.Figure:
        """
        Visualize capacity utilization over time
        
        Args:
            results: List of optimization results
            capacity_data: Dictionary with capacity information
        
        Returns:
            Plotly figure
        """
        df = pd.DataFrame(results)
        
        # Calculate used capacity
        df['used_capacity'] = df['q_case_pack'] + df['r_residual_units']
        
        time_capacity = df.groupby('time_period')['used_capacity'].sum().reset_index()
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=time_capacity['time_period'],
            y=time_capacity['used_capacity'],
            name='Used Capacity',
            marker_color='lightblue'
        ))
        
        fig.update_layout(
            title='Capacity Utilization Over Time',
            xaxis_title='Time Period',
            yaxis_title='Units',
            template='plotly_white'
        )
        
        return fig
    
    @staticmethod
    def create_decision_variables_summary(results: List[Dict[str, Any]]) -> go.Figure:
        """
        Summarize decision variables (q, r)
        
        Args:
            results: List of optimization results
        
        Returns:
            Plotly figure
        """
        df = pd.DataFrame(results)
        
        summary = df.groupby('time_period').agg({
            'q_case_pack': 'sum',
            'r_residual_units': 'sum'
        }).reset_index()
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=summary['time_period'],
            y=summary['q_case_pack'],
            mode='lines+markers',
            name='Case Packs (q)',
            line=dict(color='green', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=summary['time_period'],
            y=summary['r_residual_units'],
            mode='lines+markers',
            name='Residual Units (r)',
            line=dict(color='purple', width=2)
        ))
        
        fig.update_layout(
            title='Decision Variables Over Time',
            xaxis_title='Time Period',
            yaxis_title='Quantity',
            hovermode='x unified',
            template='plotly_white'
        )
        
        return fig
