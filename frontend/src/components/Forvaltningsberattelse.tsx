import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { CheckCircle, AlertCircle, Building, FileText, Send, Download } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface ManagementReportData {
  businessDescription: string;
  significantEvents: string;
  developmentWork: string;
  financialPosition: {
    liquidity: string;
    profitability: string;
    solvency: string;
  };
  riskManagement: string;
  futureOutlook: string;
  environmentalImpact?: string;
  personnelInformation?: string;
}

interface ManagementReportTemplate {
  [key: string]: {
    description: string;
    content: string | object;
    required: boolean;
    maxLength?: number;
  };
}

interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  fieldCount: number;
  validatedAt: string;
}

interface CompanyInfo {
  organizationNumber: string;
  companyName: string;
  latestEvent?: any;
  status?: string;
}

export function Forvaltningsberattelse() {
  const { toast } = useToast();
  
  // State management
  const [orgNumber, setOrgNumber] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [fiscalYear, setFiscalYear] = useState(new Date().getFullYear() - 1);
  const [template, setTemplate] = useState<ManagementReportTemplate | null>(null);
  const [reportData, setReportData] = useState<ManagementReportData>({
    businessDescription: '',
    significantEvents: '',
    developmentWork: '',
    financialPosition: {
      liquidity: '',
      profitability: '',
      solvency: ''
    },
    riskManagement: '',
    futureOutlook: '',
    environmentalImpact: '',
    personnelInformation: ''
  });
  
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('company');

  // Load template on component mount
  useEffect(() => {
    loadTemplate();
  }, []);

  const loadTemplate = async () => {
    try {
      const response = await fetch('/api/forvaltningsberattelse/template');
      if (response.ok) {
        const data = await response.json();
        setTemplate(data.template);
      } else {
        toast({
          title: "Fel",
          description: "Kunde inte ladda mall för förvaltningsberättelse",
          variant: "destructive"
        });
      }
    } catch (error) {
      console.error('Error loading template:', error);
      toast({
        title: "Fel",
        description: "Nätverksfel vid laddning av mall",
        variant: "destructive"
      });
    }
  };

  const fetchCompanyInfo = async () => {
    if (!orgNumber || orgNumber.length !== 10) {
      toast({
        title: "Fel",
        description: "Organisationsnummer måste vara 10 siffror",
        variant: "destructive"
      });
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`/api/bolagsverket/company/${orgNumber}`);
      if (response.ok) {
        const data = await response.json();
        setCompanyInfo(data.company_info);
        setCompanyName(data.company_info.companyName || '');
        toast({
          title: "Framgång",
          description: "Företagsinformation hämtad från Bolagsverket",
        });
      } else if (response.status === 404) {
        toast({
          title: "Inte hittat",
          description: "Ingen information hittades för detta organisationsnummer",
          variant: "destructive"
        });
      } else {
        throw new Error('Failed to fetch company info');
      }
    } catch (error) {
      console.error('Error fetching company info:', error);
      toast({
        title: "Fel",
        description: "Kunde inte hämta företagsinformation",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const validateReport = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/forvaltningsberattelse/validate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(reportData),
      });

      if (response.ok) {
        const data = await response.json();
        setValidationResult(data.validation_result);
        
        if (data.validation_result.valid) {
          toast({
            title: "Validering klar",
            description: "Förvaltningsberättelsen är korrekt ifylld",
          });
        } else {
          toast({
            title: "Valideringsfel",
            description: `${data.validation_result.errors.length} fel hittades`,
            variant: "destructive"
          });
        }
      } else {
        throw new Error('Validation failed');
      }
    } catch (error) {
      console.error('Error validating report:', error);
      toast({
        title: "Fel",
        description: "Kunde inte validera rapporten",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const submitReport = async () => {
    if (!validationResult?.valid) {
      toast({
        title: "Valideringsfel",
        description: "Vänligen åtgärda alla fel innan inlämning",
        variant: "destructive"
      });
      return;
    }

    setIsLoading(true);
    try {
      const submitData = {
        organization_number: orgNumber,
        company_name: companyName,
        fiscal_year: fiscalYear,
        management_report: reportData
      };

      const response = await fetch('/api/forvaltningsberattelse/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(submitData),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          toast({
            title: "Framgång",
            description: `Förvaltningsberättelse skickad till Bolagsverket. ID: ${data.submission_id}`,
          });
        } else {
          toast({
            title: "Fel",
            description: data.message,
            variant: "destructive"
          });
        }
      } else {
        throw new Error('Submission failed');
      }
    } catch (error) {
      console.error('Error submitting report:', error);
      toast({
        title: "Fel",
        description: "Kunde inte skicka rapporten till Bolagsverket",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const updateReportField = (field: string, value: string) => {
    if (field.includes('.')) {
      const [parent, child] = field.split('.');
      setReportData(prev => ({
        ...prev,
        [parent]: {
          ...prev[parent as keyof ManagementReportData],
          [child]: value
        }
      }));
    } else {
      setReportData(prev => ({
        ...prev,
        [field]: value
      }));
    }
  };

  const getFieldValue = (field: string): string => {
    if (field.includes('.')) {
      const [parent, child] = field.split('.');
      return (reportData[parent as keyof ManagementReportData] as any)?.[child] || '';
    }
    return reportData[field as keyof ManagementReportData] as string || '';
  };

  const renderTemplateField = (fieldKey: string, fieldData: any) => {
    const isRequired = fieldData.required;
    const maxLength = fieldData.maxLength;
    const currentValue = getFieldValue(fieldKey);
    const charCount = currentValue.length;

    if (fieldKey === 'financialPosition') {
      return (
        <div key={fieldKey} className="space-y-4">
          <Label className="text-sm font-medium">
            {fieldData.description}
            {isRequired && <span className="text-red-500 ml-1">*</span>}
          </Label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {['liquidity', 'profitability', 'solvency'].map((subField) => (
              <div key={subField} className="space-y-2">
                <Label className="text-xs text-gray-600 capitalize">
                  {subField === 'liquidity' && 'Likviditet'}
                  {subField === 'profitability' && 'Lönsamhet'}
                  {subField === 'solvency' && 'Soliditet'}
                </Label>
                <Textarea
                  value={getFieldValue(`financialPosition.${subField}`)}
                  onChange={(e) => updateReportField(`financialPosition.${subField}`, e.target.value)}
                  placeholder={`Beskriv ${subField}...`}
                  className="min-h-[100px]"
                />
              </div>
            ))}
          </div>
        </div>
      );
    }

    return (
      <div key={fieldKey} className="space-y-2">
        <Label className="text-sm font-medium">
          {fieldData.description}
          {isRequired && <span className="text-red-500 ml-1">*</span>}
        </Label>
        <Textarea
          value={currentValue}
          onChange={(e) => updateReportField(fieldKey, e.target.value)}
          placeholder={`Beskriv ${fieldData.description.toLowerCase()}...`}
          className="min-h-[120px]"
          maxLength={maxLength}
        />
        {maxLength && (
          <div className="text-xs text-gray-500 text-right">
            {charCount}/{maxLength} tecken
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold text-gray-900">Förvaltningsberättelse</h1>
        <p className="text-gray-600">Skapa och skicka förvaltningsberättelse till Bolagsverket</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="company" className="flex items-center gap-2">
            <Building className="w-4 h-4" />
            Företag
          </TabsTrigger>
          <TabsTrigger value="report" className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Rapport
          </TabsTrigger>
          <TabsTrigger value="validate" className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4" />
            Validera
          </TabsTrigger>
          <TabsTrigger value="submit" className="flex items-center gap-2">
            <Send className="w-4 h-4" />
            Skicka
          </TabsTrigger>
        </TabsList>

        <TabsContent value="company" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Företagsinformation</CardTitle>
              <CardDescription>
                Ange organisationsnummer för att hämta företagsinformation från Bolagsverket
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-4">
                <div className="flex-1">
                  <Label htmlFor="orgNumber">Organisationsnummer</Label>
                  <Input
                    id="orgNumber"
                    value={orgNumber}
                    onChange={(e) => setOrgNumber(e.target.value.replace(/\D/g, '').slice(0, 10))}
                    placeholder="5555555555"
                    maxLength={10}
                  />
                </div>
                <div className="flex-1">
                  <Label htmlFor="fiscalYear">Räkenskapsår</Label>
                  <Input
                    id="fiscalYear"
                    type="number"
                    value={fiscalYear}
                    onChange={(e) => setFiscalYear(parseInt(e.target.value))}
                    min={2020}
                    max={new Date().getFullYear()}
                  />
                </div>
              </div>
              
              <Button 
                onClick={fetchCompanyInfo}
                disabled={isLoading || orgNumber.length !== 10}
                className="w-full"
              >
                {isLoading ? 'Hämtar...' : 'Hämta företagsinformation'}
              </Button>

              {companyInfo && (
                <Card className="mt-4">
                  <CardContent className="pt-6">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-sm font-medium">Företagsnamn</Label>
                        <Input
                          value={companyName}
                          onChange={(e) => setCompanyName(e.target.value)}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label className="text-sm font-medium">Status</Label>
                        <div className="mt-1">
                          <Badge variant={companyInfo.status === 'SUBMITTED' ? 'default' : 'secondary'}>
                            {companyInfo.status || 'Okänd'}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="report" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Förvaltningsberättelse</CardTitle>
              <CardDescription>
                Fyll i alla obligatoriska avsnitt för förvaltningsberättelsen
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {template && Object.entries(template).map(([key, value]) => 
                renderTemplateField(key, value)
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="validate" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Validering</CardTitle>
              <CardDescription>
                Kontrollera att alla obligatoriska fält är ifyllda korrekt
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button 
                onClick={validateReport}
                disabled={isLoading}
                className="w-full"
              >
                {isLoading ? 'Validerar...' : 'Validera rapport'}
              </Button>

              {validationResult && (
                <div className="space-y-4">
                  <Separator />
                  
                  <div className="flex items-center gap-2">
                    {validationResult.valid ? (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-500" />
                    )}
                    <span className="font-medium">
                      {validationResult.valid ? 'Validering lyckades' : 'Valideringsfel'}
                    </span>
                  </div>

                  {validationResult.errors.length > 0 && (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        <div className="space-y-1">
                          <div className="font-medium">Fel som måste åtgärdas:</div>
                          <ul className="list-disc list-inside space-y-1">
                            {validationResult.errors.map((error, index) => (
                              <li key={index} className="text-sm">{error}</li>
                            ))}
                          </ul>
                        </div>
                      </AlertDescription>
                    </Alert>
                  )}

                  {validationResult.warnings.length > 0 && (
                    <Alert>
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        <div className="space-y-1">
                          <div className="font-medium">Varningar:</div>
                          <ul className="list-disc list-inside space-y-1">
                            {validationResult.warnings.map((warning, index) => (
                              <li key={index} className="text-sm">{warning}</li>
                            ))}
                          </ul>
                        </div>
                      </AlertDescription>
                    </Alert>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="submit" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Skicka till Bolagsverket</CardTitle>
              <CardDescription>
                Granska och skicka förvaltningsberättelsen till Bolagsverket
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-gray-50 p-4 rounded-lg space-y-2">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Organisationsnummer:</span> {orgNumber}
                  </div>
                  <div>
                    <span className="font-medium">Företagsnamn:</span> {companyName}
                  </div>
                  <div>
                    <span className="font-medium">Räkenskapsår:</span> {fiscalYear}
                  </div>
                  <div>
                    <span className="font-medium">Status:</span> 
                    {validationResult?.valid ? (
                      <Badge className="ml-2" variant="default">Redo för inlämning</Badge>
                    ) : (
                      <Badge className="ml-2" variant="destructive">Behöver valideras</Badge>
                    )}
                  </div>
                </div>
              </div>

              <Button 
                onClick={submitReport}
                disabled={isLoading || !validationResult?.valid}
                className="w-full"
                size="lg"
              >
                {isLoading ? 'Skickar...' : 'Skicka till Bolagsverket'}
              </Button>

              <p className="text-xs text-gray-600 text-center">
                Genom att klicka "Skicka till Bolagsverket" bekräftar du att all information är korrekt 
                och att du har behörighet att lämna in förvaltningsberättelsen för detta företag.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

