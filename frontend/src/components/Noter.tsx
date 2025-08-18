import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Switch } from '@/components/ui/switch';

interface NoterItem {
  row_id: number;
  row_title: string;
  current_amount: number;
  previous_amount: number;
  variable_name: string;
  show_tag: boolean;
  accounts_included: string;
  account_details?: Array<{
    account_id: string;
    account_text: string;
    balance: number;
  }>;
  block: string;
  always_show: boolean;
  toggle_show: boolean;
  style: string;
}

interface NoterProps {
  noterData: NoterItem[];
  fiscalYear?: number;
  previousYear?: number;
}

export function Noter({ noterData, fiscalYear, previousYear }: NoterProps) {
  const [blockToggles, setBlockToggles] = useState<Record<string, boolean>>({});
  const [selectedItem, setSelectedItem] = useState<NoterItem | null>(null);

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('sv-SE', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatAmountWithDecimals = (amount: number) => {
    return new Intl.NumberFormat('sv-SE', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  // Group items by block
  const groupedItems = noterData.reduce((groups: Record<string, NoterItem[]>, item) => {
    const block = item.block || 'Övriga noter';
    if (!groups[block]) {
      groups[block] = [];
    }
    groups[block].push(item);
    return groups;
  }, {});

  // Get unique blocks for toggle controls
  const blocks = Object.keys(groupedItems);

  // Filter items based on toggle states
  const getVisibleItems = (blockItems: NoterItem[]) => {
    return blockItems.filter(item => {
      if (item.always_show) return true;
      if (item.toggle_show && blockToggles[item.block]) return true;
      return false;
    });
  };

  const AccountDetailsDialog = ({ item }: { item: NoterItem }) => (
    <Dialog>
      <DialogTrigger asChild>
        <Badge 
          variant="secondary" 
          className="ml-2 cursor-pointer hover:bg-gray-200 text-xs"
          onClick={() => setSelectedItem(item)}
        >
          SHOW
        </Badge>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{item.row_title} - Kontodetaljer</DialogTitle>
        </DialogHeader>
        <div className="mt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Konto</TableHead>
                <TableHead>Kontotext</TableHead>
                <TableHead className="text-right">{fiscalYear || new Date().getFullYear()}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {item.account_details?.map((detail, index) => (
                <TableRow key={index}>
                  <TableCell className="font-mono">{detail.account_id}</TableCell>
                  <TableCell>{detail.account_text}</TableCell>
                  <TableCell className="text-right font-mono">
                    {formatAmountWithDecimals(detail.balance)}
                  </TableCell>
                </TableRow>
              ))}
              {(!item.account_details || item.account_details.length === 0) && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-gray-500">
                    Inga konton med saldo hittades
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  );

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          📝 Noter
          <span className="text-sm font-normal text-gray-600">
            ({noterData.length} poster)
          </span>
        </CardTitle>

      </CardHeader>
      
      <CardContent>
        <div className="space-y-6">
          {blocks.map(block => {
            const blockItems = groupedItems[block];
            const visibleItems = getVisibleItems(blockItems);
            
            if (visibleItems.length === 0) return null;
            
            // Get first row title for block heading
            const firstRowTitle = blockItems[0]?.row_title || block;
            const blockHeading = `Not ${firstRowTitle}`;
            
            return (
              <div key={block} className="space-y-2">
                <div className="flex items-center justify-between border-b pb-1">
                  <h3 className="font-semibold text-lg">{blockHeading}</h3>
                  <div className="flex items-center space-x-2">
                    <Switch
                      id={`toggle-${block}`}
                      checked={blockToggles[block] || false}
                      onCheckedChange={(checked) => 
                        setBlockToggles(prev => ({ ...prev, [block]: checked }))
                      }
                    />
                    <label 
                      htmlFor={`toggle-${block}`} 
                      className="text-sm font-medium cursor-pointer"
                    >
                      Visa detaljer
                    </label>
                  </div>
                </div>
                
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-1/2">Beskrivning</TableHead>
                      <TableHead className="text-right w-1/4">
                        {fiscalYear || new Date().getFullYear()}
                      </TableHead>
                      <TableHead className="text-right w-1/4">
                        {previousYear || (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1)}
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {visibleItems.map((item, index) => {
                      // Apply style classes based on item.style
                      const getStyleClasses = (style: string) => {
                        let classes = '';
                        const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
                        if (boldStyles.includes(style)) {
                          classes += ' font-semibold';
                        }
                        const lineStyles = ['S2','S3','TS2','TS3'];
                        if (lineStyles.includes(style)) {
                          classes += ' border-t border-b border-gray-300';
                        }
                        return classes;
                      };
                      
                      const rowClasses = getStyleClasses(item.style || '');
                      const isHeading = item.style && ['H0', 'H1', 'H2', 'H3', 'S1', 'S2', 'S3'].includes(item.style);
                      
                      return (
                        <TableRow key={index} className={rowClasses}>
                          <TableCell className={`${isHeading ? 'font-bold' : 'font-medium'}`}>
                            {item.row_title}
                            {item.show_tag && (
                              <AccountDetailsDialog item={item} />
                            )}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {formatAmount(item.current_amount)} kr
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {formatAmount(item.previous_amount)} kr
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            );
          })}
          
          {blocks.every(block => getVisibleItems(groupedItems[block]).length === 0) && (
            <div className="text-center text-gray-500 py-4">
              Inga noter att visa. Aktivera sektioner ovan för att se detaljer.
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
