import React, { useState, useEffect } from 'react';
import { apiService } from '@/services/api';

interface PeriodiseringsfonderItem {
  variable_name: string;
  row_title: string;
  header: boolean;
  always_show: boolean;
  show_amount: boolean;
  is_calculated: boolean;
  amount: number;
}

interface PeriodiseringsfonderProps {
  companyData: any;
  onDataUpdate?: (updates: any) => void;
}

export function Periodiseringsfonder({ companyData, onDataUpdate }: PeriodiseringsfonderProps) {
  const [periodiseringsfonderData, setPeriodiseringsfonderData] = useState<PeriodiseringsfonderItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatAmount = (amount: number): string => {
    if (amount === 0 || amount === -0) {
      return '0 kr';
    }
    return new Intl.NumberFormat('sv-SE', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(Math.abs(amount)) + ' kr';
  };

  const calculatePeriodiseringsfonder = async () => {
    if (!companyData?.seFileData?.current_accounts) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await apiService.calculatePeriodiseringsfonder({
        current_accounts: companyData.seFileData.current_accounts
      });

      if (result.success) {
        setPeriodiseringsfonderData(result.periodiseringsfonder_data);
        onDataUpdate?.({ periodiseringsfonderData: result.periodiseringsfonder_data });
      }
    } catch (err) {
      console.error('Error calculating periodiseringsfonder:', err);
      setError('Kunde inte beräkna periodiseringsfonder');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (companyData?.seFileData?.current_accounts && companyData?.showPeriodiseringsfonder) {
      calculatePeriodiseringsfonder();
    }
  }, [companyData?.seFileData?.current_accounts, companyData?.showPeriodiseringsfonder]);

  // Don't render if not shown or no data
  if (!companyData?.showPeriodiseringsfonder || (!periodiseringsfonderData.length && !isLoading)) {
    return null;
  }

  // Filter items based on always_show and amount
  const visibleItems = periodiseringsfonderData.filter(item => {
    if (item.header) return true;
    if (item.always_show) return true;
    return item.amount !== 0 && item.amount !== null && item.amount !== undefined;
  });

  if (isLoading) {
    return (
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-6 mt-6">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500"></div>
          <span className="ml-2 text-purple-700">Beräknar periodiseringsfonder...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 mt-6">
        <div className="text-red-700">{error}</div>
      </div>
    );
  }

  return (
    <div className="bg-purple-50 border border-purple-200 rounded-lg p-6 mt-6" data-section="periodiseringsfonder">
      <h3 className="text-lg font-semibold text-purple-800 mb-4">
        📊 Periodiseringsfonder
      </h3>
      
      <div className="space-y-2">
        {visibleItems.map((item, index) => (
          <div key={item.variable_name} className={`flex justify-between items-center py-2 ${
            item.header ? 'font-semibold text-purple-800 border-b border-purple-300' : 'text-purple-700'
          }`}>
            <span className="text-sm">
              {item.row_title}
            </span>
            {item.show_amount && !item.header && (
              <span className="text-sm font-medium">
                {formatAmount(item.amount)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
