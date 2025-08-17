import { API_ENDPOINTS } from '@/config/api';

export interface UploadResponse {
  success: boolean;
  company_data: any;
  message: string;
}

export interface TestParserResponse {
  success: boolean;
  company_info: any;
  current_accounts_count: number;
  previous_accounts_count: number;
  current_accounts_sample: Record<string, number>;
  previous_accounts_sample: Record<string, number>;
  rr_count: number;
  rr_sample: any[];
  br_count: number;
  br_sample: any[];
  message: string;
}

class ApiService {
  private async makeRequest<T>(
    url: string, 
    options: RequestInit = {}
  ): Promise<T> {
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async uploadSeFile(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(API_ENDPOINTS.uploadSeFile, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }

    return await response.json();
  }

  async testParser(file: File): Promise<TestParserResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(API_ENDPOINTS.testParser, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Parser test failed: ${response.status}`);
    }

    return await response.json();
  }

  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.makeRequest(API_ENDPOINTS.health);
  }

  async getCompanyInfo(orgNumber: string): Promise<any> {
    return this.makeRequest(`${API_ENDPOINTS.companyInfo}/${orgNumber}`);
  }

  async getChatFlowStep(stepNumber: number) {
    try {
      const response = await this.makeRequest(`${API_ENDPOINTS.chatFlow}/${stepNumber}`);
      return response;
    } catch (error) {
      console.error('Error getting chat flow step:', error);
      throw error;
    }
  }

  async getNextChatFlowStep(currentStep: number): Promise<{
    success: boolean;
    question?: any;
    options?: any[];
    next_step?: number;
  }> {
    return this.makeRequest(`${API_ENDPOINTS.chatFlow}/next/${currentStep}`);
  }

  async processChatChoice(data: {
    step_number: number;
    option_value: string;
    context?: Record<string, any>;
  }): Promise<{
    success: boolean;
    result: {
      action_type: string;
      action_data?: any;
      next_step?: number;
    };
  }> {
    return this.makeRequest(`${API_ENDPOINTS.chatFlow}/process-choice`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async recalculateInk2(data: {
    current_accounts: Record<string, number>;
    fiscal_year?: number;
    rr_data: any[];
    br_data: any[];
    manual_amounts: Record<string, number>;
    justering_sarskild_loneskatt?: number;
    ink4_14a_outnyttjat_underskott?: number;
    ink4_16_underskott_adjustment?: number;
  }): Promise<{ success: boolean; ink2_data: any[] }> {
    return this.makeRequest(API_ENDPOINTS.recalculateInk2, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Förvaltningsberättelse API methods
  async getManagementReportTemplate(): Promise<{ success: boolean; template: any; message: string }> {
    return this.makeRequest(API_ENDPOINTS.managementReportTemplate);
  }

  async validateManagementReport(reportData: any): Promise<{ success: boolean; validation_result: any; message: string }> {
    return this.makeRequest(API_ENDPOINTS.managementReportValidate, {
      method: 'POST',
      body: JSON.stringify(reportData),
    });
  }

  async submitManagementReport(reportRequest: any): Promise<{ success: boolean; validation_result: any; submission_id?: string; message: string }> {
    return this.makeRequest(API_ENDPOINTS.managementReportSubmit, {
      method: 'POST',
      body: JSON.stringify(reportRequest),
    });
  }

  async getCompanyInfoFromBolagsverket(orgNumber: string): Promise<{ success: boolean; company_info: any; message: string }> {
    return this.makeRequest(`${API_ENDPOINTS.bolagsverketCompany}/${orgNumber}`);
  }

  async getCompanyDocumentsFromBolagsverket(orgNumber: string): Promise<{ success: boolean; document_list: any; message: string }> {
    return this.makeRequest(`${API_ENDPOINTS.bolagsverketDocuments}/${orgNumber}`);
  }

  async getDocumentFromBolagsverket(documentId: string): Promise<{ success: boolean; document: any; message: string }> {
    return this.makeRequest(`${API_ENDPOINTS.bolagsverketDocument}/${documentId}`);
  }

  async checkBolagsverketHealth(): Promise<{ success: boolean; healthy: boolean; message: string }> {
    return this.makeRequest(API_ENDPOINTS.bolagsverketHealth);
  }
}

export const apiService = new ApiService();