"""
Trend Analysis Module for Attendance Patterns
Provides weekly, monthly, yearly trends and forecasting capabilities
"""

import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session


class TrendAnalyzer:
    """Analyze attendance trends and provide forecasts"""
    
    def __init__(self):
        self.trend_periods = {
            'weekly': 7,
            'monthly': 30,
            'quarterly': 90,
            'yearly': 365
        }
    
    def analyze_employee_trends(self, attendance_records, user_id: int) -> Dict:
        """
        Analyze attendance trends for a single employee
        
        Returns:
        - Weekly trend (last 7 days)
        - Monthly trend (last 30 days)
        - Quarterly trend (last 90 days)
        - Yearly trend (last 365 days)
        - Trend direction (improving, stable, declining)
        - Forecast for next 7 days
        """
        if not attendance_records:
            return {
                'user_id': user_id,
                'error': 'Insufficient data for trend analysis'
            }
        
        # Sort records by date
        records = sorted(attendance_records, key=lambda r: r.date)
        today = date.today()
        
        trends = {
            'user_id': user_id,
            'analysis_date': today.isoformat(),
            'total_records': len(records)
        }
        
        # Calculate trends for different periods
        for period_name, days in self.trend_periods.items():
            cutoff_date = today - timedelta(days=days)
            period_records = [r for r in records if r.date >= cutoff_date]
            
            if period_records:
                trend_data = self._calculate_period_trend(period_records)
                trends[f'{period_name}_trend'] = trend_data
        
        # Calculate trend direction
        trends['trend_direction'] = self._calculate_trend_direction(
            trends.get('weekly_trend', {}),
            trends.get('monthly_trend', {}),
            trends.get('quarterly_trend', {})
        )
        
        # Generate forecast
        trends['forecast_7days'] = self._forecast_next_n_days(records, 7)
        trends['forecast_30days'] = self._forecast_next_n_days(records, 30)
        
        return trends
    
    def _calculate_period_trend(self, records) -> Dict:
        """Calculate metrics for a time period"""
        total_days = len(records)
        present_days = sum(1 for r in records if r.status in ['Present', 'Late'])
        absent_days = sum(1 for r in records if r.status == 'Absent')
        late_days = sum(1 for r in records if r.status == 'Late')
        
        working_hours = [r.working_hours for r in records if r.working_hours > 0]
        avg_working_hours = np.mean(working_hours) if working_hours else 0
        
        return {
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'late_days': late_days,
            'attendance_rate': round(present_days / total_days * 100, 2) if total_days > 0 else 0,
            'absence_rate': round(absent_days / total_days * 100, 2) if total_days > 0 else 0,
            'lateness_rate': round(late_days / total_days * 100, 2) if total_days > 0 else 0,
            'avg_working_hours': round(avg_working_hours, 2)
        }
    
    def _calculate_trend_direction(self, weekly: Dict, monthly: Dict, quarterly: Dict) -> Dict:
        """
        Determine if trends are improving, stable, or declining
        
        Rules:
        - Improving: attendance rate increasing week over month
        - Stable: attendance rate within ±5% of monthly average
        - Declining: attendance rate dropping compared to quarterly
        """
        if not all([weekly, monthly, quarterly]):
            return {'direction': 'insufficient_data', 'confidence': 0}
        
        weekly_rate = weekly.get('attendance_rate', 0)
        monthly_rate = monthly.get('attendance_rate', 0)
        quarterly_rate = quarterly.get('attendance_rate', 0)
        
        # Calculate change percentages
        weekly_vs_monthly = weekly_rate - monthly_rate
        monthly_vs_quarterly = monthly_rate - quarterly_rate
        
        # Determine direction
        if abs(weekly_vs_monthly) <= 5 and abs(monthly_vs_quarterly) <= 5:
            direction = 'stable'
            confidence = 80
        elif weekly_vs_monthly > 5 and monthly_vs_quarterly > 2:
            direction = 'improving'
            confidence = 75
        elif weekly_vs_monthly < -5 or monthly_vs_quarterly < -5:
            direction = 'declining'
            confidence = 85
        elif weekly_vs_monthly > 2:
            direction = 'slightly_improving'
            confidence = 60
        elif weekly_vs_monthly < -2:
            direction = 'slightly_declining'
            confidence = 65
        else:
            direction = 'stable'
            confidence = 70
        
        return {
            'direction': direction,
            'confidence': confidence,
            'weekly_vs_monthly_change': round(weekly_vs_monthly, 2),
            'monthly_vs_quarterly_change': round(monthly_vs_quarterly, 2)
        }
    
    def _forecast_next_n_days(self, records, n_days: int) -> Dict:
        """
        Forecast attendance for the next n days using simple moving average
        """
        if len(records) < 7:
            return {'forecast_days': n_days, 'error': 'Insufficient historical data'}
        
        # Calculate recent 7-day average
        recent_records = records[-7:]
        recent_attendance_rate = sum(
            1 for r in recent_records if r.status in ['Present', 'Late']
        ) / len(recent_records)
        
        # Simple forecast: assume similar attendance pattern
        expected_present_days = int(n_days * recent_attendance_rate)
        expected_absent_days = n_days - expected_present_days
        
        # Calculate confidence based on data consistency
        recent_variance = np.var([
            1 if r.status in ['Present', 'Late'] else 0 for r in recent_records
        ])
        confidence = max(50, 100 - (recent_variance * 50))
        
        return {
            'forecast_days': n_days,
            'expected_present_days': expected_present_days,
            'expected_absent_days': expected_absent_days,
            'expected_attendance_rate': round(recent_attendance_rate * 100, 2),
            'confidence': round(confidence, 2),
            'method': 'moving_average'
        }
    
    def analyze_department_trends(self, records_by_employee: Dict[int, List]) -> Dict:
        """
        Analyze trends for entire department
        
        Args:
            records_by_employee: Dict mapping user_id to their attendance records
        """
        department_trends = {
            'analysis_date': datetime.now().isoformat(),
            'total_employees': len(records_by_employee),
            'employee_count': len(records_by_employee)
        }
        
        # Aggregate metrics
        all_attendance_rates = []
        all_absent_rates = []
        all_late_rates = []
        
        for user_id, records in records_by_employee.items():
            if records:
                trend = self._calculate_period_trend(records)
                all_attendance_rates.append(trend['attendance_rate'])
                all_absent_rates.append(trend['absence_rate'])
                all_late_rates.append(trend['lateness_rate'])
        
        if all_attendance_rates:
            department_trends['avg_attendance_rate'] = round(np.mean(all_attendance_rates), 2)
            department_trends['avg_absence_rate'] = round(np.mean(all_absent_rates), 2)
            department_trends['avg_lateness_rate'] = round(np.mean(all_late_rates), 2)
            department_trends['attendance_std'] = round(np.std(all_attendance_rates), 2)
            
            # Identify outliers
            attendance_mean = np.mean(all_attendance_rates)
            attendance_std = np.std(all_attendance_rates)
            
            outlier_threshold = 2  # 2 standard deviations
            department_trends['high_performers'] = sum(
                1 for rate in all_attendance_rates 
                if rate > attendance_mean + (attendance_std * outlier_threshold)
            )
            department_trends['at_risk_employees'] = sum(
                1 for rate in all_attendance_rates 
                if rate < attendance_mean - (attendance_std * outlier_threshold)
            )
        
        return department_trends
    
    def detect_seasonal_patterns(self, records, user_id: int) -> Dict:
        """
        Detect seasonal patterns (Monday/Friday effect, seasonal absences)
        """
        if len(records) < 30:
            return {'error': 'Insufficient data for seasonal analysis'}
        
        patterns = {
            'user_id': user_id,
            'by_day_of_week': {},
            'by_month': {}
        }
        
        # Analyze by day of week
        for day in range(7):
            day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][day]
            day_records = [r for r in records if r.date.weekday() == day]
            
            if day_records:
                attendance_rate = sum(
                    1 for r in day_records if r.status in ['Present', 'Late']
                ) / len(day_records) * 100
                
                patterns['by_day_of_week'][day_name] = {
                    'total_days': len(day_records),
                    'attendance_rate': round(attendance_rate, 2),
                    'late_days': sum(1 for r in day_records if r.status == 'Late'),
                    'absent_days': sum(1 for r in day_records if r.status == 'Absent')
                }
        
        # Analyze by month
        for month in range(1, 13):
            month_name = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ][month - 1]
            
            month_records = [r for r in records if r.date.month == month]
            
            if month_records:
                attendance_rate = sum(
                    1 for r in month_records if r.status in ['Present', 'Late']
                ) / len(month_records) * 100
                
                patterns['by_month'][month_name] = {
                    'total_days': len(month_records),
                    'attendance_rate': round(attendance_rate, 2),
                    'absent_days': sum(1 for r in month_records if r.status == 'Absent')
                }
        
        return patterns


# Module-level functions for easy integration

def get_employee_trends(user_id: int, db: Session) -> Dict:
    """Get comprehensive trend analysis for an employee"""
    from .database import Attendance
    
    records = db.query(Attendance).filter(Attendance.user_id == user_id).all()
    analyzer = TrendAnalyzer()
    return analyzer.analyze_employee_trends(records, user_id)

def get_seasonal_patterns(user_id: int, db: Session) -> Dict:
    """Get seasonal pattern analysis for an employee"""
    from .database import Attendance
    
    records = db.query(Attendance).filter(Attendance.user_id == user_id).all()
    analyzer = TrendAnalyzer()
    return analyzer.detect_seasonal_patterns(records, user_id)

def get_department_trends(department: str, db: Session) -> Dict:
    """Get trend analysis for entire department"""
    from .database import Attendance, User
    
    users = db.query(User).filter(User.department == department).all()
    records_by_employee = {}
    
    for user in users:
        records = db.query(Attendance).filter(Attendance.user_id == user.id).all()
        records_by_employee[user.id] = records
    
    analyzer = TrendAnalyzer()
    return analyzer.analyze_department_trends(records_by_employee)
