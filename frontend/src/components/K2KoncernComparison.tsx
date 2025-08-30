import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface K2KoncernData {
  koncern_ib: number;
  koncern_ub: number;
  inkop_koncern: number;
  red_varde_koncern: number;
  source: string;
}

interface K2KoncernComparisonData {
  current_logic: K2KoncernData;
  original_logic: K2KoncernData;
}

interface K2KoncernComparisonProps {
  companyId: string;
  seFileData?: any;
}

export function K2KoncernComparison({ companyId, seFileData }: K2KoncernComparisonProps) {
  const [comparisonData, setComparisonData] = useState<K2KoncernComparisonData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('sv-SE', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const fetchComparison = async () => {
    if (!companyId || companyId === 'unknown') return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/k2-koncern-comparison/${companyId}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setComparisonData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Error fetching K2 koncern comparison:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchComparison();
  }, [companyId]);

  const getDifferenceColor = (current: number, original: number) => {
    const diff = Math.abs(current - original);
    if (diff < 1) return 'text-green-600';
    if (diff < 1000) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getDifference = (current: number, original: number) => {
    const diff = current - original;
    if (Math.abs(diff) < 1) return '≈ 0';
    return diff > 0 ? `+${formatAmount(diff)}` : formatAmount(diff);
  };

  if (!companyId || companyId === 'unknown') {
    return null;
  }

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-orange-500" />
            K2 Koncern Logic Comparison (Debug)
          </CardTitle>
          <p className="text-sm text-muted-foreground mt-1">
            Comparing current logic vs original pre-preclass logic
          </p>
        </div>
        <Button 
          variant="outline" 
          size="sm" 
          onClick={fetchComparison}
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </CardHeader>
      
      <CardContent>
        {loading && (
          <div className="text-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
            <p className="text-sm text-muted-foreground mt-2">Loading comparison...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800 text-sm">
              <strong>Error:</strong> {error}
            </p>
          </div>
        )}

        {comparisonData && !loading && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Headers */}
              <div className="font-medium text-sm text-muted-foreground">
                K2 Koncern Variable
              </div>
              <div className="font-medium text-sm text-muted-foreground text-center">
                Current Logic
                <Badge variant="outline" className="ml-2 text-xs">
                  {comparisonData.current_logic.source}
                </Badge>
              </div>
              <div className="font-medium text-sm text-muted-foreground text-center">
                Original Logic
                <Badge variant="outline" className="ml-2 text-xs">
                  {comparisonData.original_logic.source}
                </Badge>
              </div>

              {/* Data rows */}
              {[
                { key: 'koncern_ib', label: 'Koncern IB' },
                { key: 'koncern_ub', label: 'Koncern UB' },
                { key: 'inkop_koncern', label: 'Inköp Koncern' },
                { key: 'red_varde_koncern', label: 'Redovisat Värde' },
              ].map(({ key, label }) => {
                const currentValue = comparisonData.current_logic[key as keyof K2KoncernData] as number;
                const originalValue = comparisonData.original_logic[key as keyof K2KoncernData] as number;
                const diffColor = getDifferenceColor(currentValue, originalValue);
                const difference = getDifference(currentValue, originalValue);
                
                return (
                  <React.Fragment key={key}>
                    <div className="py-2 font-medium">
                      {label}
                    </div>
                    <div className="py-2 text-center font-mono">
                      {formatAmount(currentValue)}
                    </div>
                    <div className="py-2 text-center font-mono">
                      {formatAmount(originalValue)}
                      {Math.abs(currentValue - originalValue) >= 1 && (
                        <div className={`text-xs mt-1 ${diffColor}`}>
                          Diff: {difference}
                        </div>
                      )}
                    </div>
                  </React.Fragment>
                );
              })}
            </div>

            {/* Summary */}
            <div className="mt-4 p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-muted-foreground">
                <strong>Purpose:</strong> This comparison helps identify differences between the current K2 koncern logic 
                (which may have been affected by preclass changes) and the original working logic from before preclass implementation.
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
