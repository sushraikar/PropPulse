import React, { useState } from 'react';
import { useRouter } from 'next/router';
import { Formik, Form, Field, ErrorMessage } from 'formik';
import * as Yup from 'yup';
import { useAuth } from '../../contexts/AuthContext';
import toast from 'react-hot-toast';
import axios from 'axios';

// Define the steps in the welcome wizard
const STEPS = [
  'Company Information',
  'Contact Details',
  'Banking Information',
  'Verification',
  'Complete'
];

// Validation schemas for each step
const validationSchemas = [
  // Step 1: Company Information
  Yup.object({
    legalName: Yup.string().required('Legal name is required'),
    tradeLicenseNumber: Yup.string().required('Trade license number is required'),
    developerID: Yup.string().required('Developer ID is required'),
    vatRegistration: Yup.string().required('VAT registration number is required'),
  }),
  
  // Step 2: Contact Details
  Yup.object({
    primaryEmail: Yup.string().email('Invalid email address').required('Primary email is required'),
    primaryWhatsApp: Yup.string().required('Primary WhatsApp number is required'),
    supportPhone: Yup.string().required('Support phone number is required'),
  }),
  
  // Step 3: Banking Information
  Yup.object({
    iban: Yup.string().required('IBAN is required'),
    escrowIban: Yup.string().required('Escrow IBAN is required'),
    bankName: Yup.string().required('Bank name is required'),
    swiftCode: Yup.string().required('SWIFT code is required'),
  }),
  
  // Step 4: Verification
  Yup.object({
    termsAccepted: Yup.boolean().oneOf([true], 'You must accept the terms and conditions'),
    dataProcessingConsent: Yup.boolean().oneOf([true], 'You must consent to data processing'),
  }),
];

const WelcomeWizard = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const { user } = useAuth();
  const router = useRouter();

  // Initial form values
  const initialValues = {
    // Company Information
    legalName: '',
    tradeLicenseNumber: '',
    developerID: '',
    vatRegistration: '',
    
    // Contact Details
    primaryEmail: user?.email || '',
    primaryWhatsApp: '',
    supportPhone: '',
    
    // Banking Information
    iban: '',
    escrowIban: '',
    bankName: '',
    swiftCode: '',
    
    // Verification
    termsAccepted: false,
    dataProcessingConsent: false,
  };

  // Handle logo file change
  const handleLogoChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      const file = event.target.files[0];
      setLogoFile(file);
      
      // Create preview URL
      const reader = new FileReader();
      reader.onload = (e) => {
        setLogoPreview(e.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  // Handle form submission
  const handleSubmit = async (values: any, { setSubmitting }: any) => {
    try {
      // If this is the final step, submit the entire form
      if (currentStep === STEPS.length - 2) {
        // Create form data for file upload
        const formData = new FormData();
        
        // Add all form values
        Object.keys(values).forEach(key => {
          formData.append(key, values[key]);
        });
        
        // Add logo file if exists
        if (logoFile) {
          formData.append('logo', logoFile);
        }
        
        // Submit to API
        const response = await axios.post('/api/dev/onboarding', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });
        
        if (response.data.success) {
          toast.success('Developer profile created successfully!');
          setCurrentStep(currentStep + 1); // Move to completion step
        } else {
          toast.error(response.data.message || 'Failed to create developer profile');
        }
      } else {
        // Move to the next step
        setCurrentStep(currentStep + 1);
      }
    } catch (error: any) {
      toast.error(error.response?.data?.message || 'An error occurred');
    } finally {
      setSubmitting(false);
    }
  };

  // Go back to previous step
  const handleBack = () => {
    setCurrentStep(Math.max(0, currentStep - 1));
  };

  // Render step content
  const renderStepContent = (step: number, formikProps: any) => {
    const { values, touched, errors, handleChange, handleBlur, isSubmitting } = formikProps;
    
    switch (step) {
      case 0: // Company Information
        return (
          <div className="space-y-6">
            <div>
              <label htmlFor="logo" className="block text-sm font-medium text-gray-700 mb-1">
                Company Logo
              </label>
              <div className="flex items-center space-x-4">
                <div className="w-24 h-24 border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center overflow-hidden">
                  {logoPreview ? (
                    <img src={logoPreview} alt="Logo preview" className="w-full h-full object-contain" />
                  ) : (
                    <span className="text-gray-400 text-sm text-center">No logo uploaded</span>
                  )}
                </div>
                <input
                  type="file"
                  id="logo"
                  name="logo"
                  accept="image/*"
                  onChange={handleLogoChange}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
                />
              </div>
            </div>
            
            <div>
              <label htmlFor="legalName" className="block text-sm font-medium text-gray-700 mb-1">
                Legal Company Name
              </label>
              <Field
                type="text"
                id="legalName"
                name="legalName"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.legalName && errors.legalName ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="legalName" component="div" className="mt-1 text-sm text-red-600" />
            </div>
            
            <div>
              <label htmlFor="tradeLicenseNumber" className="block text-sm font-medium text-gray-700 mb-1">
                Trade License Number
              </label>
              <Field
                type="text"
                id="tradeLicenseNumber"
                name="tradeLicenseNumber"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.tradeLicenseNumber && errors.tradeLicenseNumber ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="tradeLicenseNumber" component="div" className="mt-1 text-sm text-red-600" />
            </div>
            
            <div>
              <label htmlFor="developerID" className="block text-sm font-medium text-gray-700 mb-1">
                Developer ID (RAK RERA / DLD)
              </label>
              <Field
                type="text"
                id="developerID"
                name="developerID"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.developerID && errors.developerID ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="developerID" component="div" className="mt-1 text-sm text-red-600" />
            </div>
            
            <div>
              <label htmlFor="vatRegistration" className="block text-sm font-medium text-gray-700 mb-1">
                VAT Registration Number
              </label>
              <Field
                type="text"
                id="vatRegistration"
                name="vatRegistration"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.vatRegistration && errors.vatRegistration ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="vatRegistration" component="div" className="mt-1 text-sm text-red-600" />
            </div>
          </div>
        );
        
      case 1: // Contact Details
        return (
          <div className="space-y-6">
            <div>
              <label htmlFor="primaryEmail" className="block text-sm font-medium text-gray-700 mb-1">
                Primary Contact Email
              </label>
              <Field
                type="email"
                id="primaryEmail"
                name="primaryEmail"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.primaryEmail && errors.primaryEmail ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="primaryEmail" component="div" className="mt-1 text-sm text-red-600" />
            </div>
            
            <div>
              <label htmlFor="primaryWhatsApp" className="block text-sm font-medium text-gray-700 mb-1">
                Primary WhatsApp Number
              </label>
              <Field
                type="text"
                id="primaryWhatsApp"
                name="primaryWhatsApp"
                placeholder="+971XXXXXXXXX"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.primaryWhatsApp && errors.primaryWhatsApp ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="primaryWhatsApp" component="div" className="mt-1 text-sm text-red-600" />
            </div>
            
            <div>
              <label htmlFor="supportPhone" className="block text-sm font-medium text-gray-700 mb-1">
                24/7 Support Phone (for buyers)
              </label>
              <Field
                type="text"
                id="supportPhone"
                name="supportPhone"
                placeholder="+971XXXXXXXXX"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.supportPhone && errors.supportPhone ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="supportPhone" component="div" className="mt-1 text-sm text-red-600" />
            </div>
          </div>
        );
        
      case 2: // Banking Information
        return (
          <div className="space-y-6">
            <div>
              <label htmlFor="iban" className="block text-sm font-medium text-gray-700 mb-1">
                IBAN
              </label>
              <Field
                type="text"
                id="iban"
                name="iban"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.iban && errors.iban ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="iban" component="div" className="mt-1 text-sm text-red-600" />
            </div>
            
            <div>
              <label htmlFor="escrowIban" className="block text-sm font-medium text-gray-700 mb-1">
                Escrow IBAN
              </label>
              <Field
                type="text"
                id="escrowIban"
                name="escrowIban"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.escrowIban && errors.escrowIban ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="escrowIban" component="div" className="mt-1 text-sm text-red-600" />
            </div>
            
            <div>
              <label htmlFor="bankName" className="block text-sm font-medium text-gray-700 mb-1">
                Bank Name
              </label>
              <Field
                type="text"
                id="bankName"
                name="bankName"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.bankName && errors.bankName ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="bankName" component="div" className="mt-1 text-sm text-red-600" />
            </div>
            
            <div>
              <label htmlFor="swiftCode" className="block text-sm font-medium text-gray-700 mb-1">
                SWIFT Code
              </label>
              <Field
                type="text"
                id="swiftCode"
                name="swiftCode"
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm ${
                  touched.swiftCode && errors.swiftCode ? 'border-red-500' : ''
                }`}
              />
              <ErrorMessage name="swiftCode" component="div" className="mt-1 text-sm text-red-600" />
            </div>
          </div>
        );
        
      case 3: // Verification
        return (
          <div className="space-y-6">
            <div className="bg-gray-50 p-4 rounded-lg">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Review Your Information</h3>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-500">Legal Name</p>
                  <p className="mt-1">{values.legalName}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">Trade License Number</p>
                  <p className="mt-1">{values.tradeLicenseNumber}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">Developer ID</p>
                  <p className="mt-1">{values.developerID}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">VAT Registration</p>
                  <p className="mt-1">{values.vatRegistration}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">Primary Email</p>
                  <p className="mt-1">{values.primaryEmail}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">Primary WhatsApp</p>
                  <p className="mt-1">{values.primaryWhatsApp}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">Support Phone</p>
                  <p className="mt-1">{values.supportPhone}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">IBAN</p>
                  <p className="mt-1">{values.iban}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">Escrow IBAN</p>
                  <p className="mt-1">{values.escrowIban}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">Bank Name</p>
                  <p className="mt-1">{values.bankName}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">SWIFT Code</p>
                  <p className="mt-1">{values.swiftCode}</p>
                </div>
              </div>
            </div>
            
            <div className="space-y-4">
              <div className="flex items-start">
                <div className="flex items-center h-5">
                  <Field
                    type="checkbox"
                    id="termsAccepted"
                    name="termsAccepted"
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                </div>
                <div className="ml-3 text-sm">
                  <label htmlFor="termsAccepted" className="font-medium text-gray-700">
                    I accept the <a href="/terms" className="text-primary-600 hover:text-primary-500">Terms and Conditions</a>
                  </label>
                  <ErrorMessage name="termsAccepted" component="div" className="mt-1 text-sm text-red-600" />
                </div>
              </div>
              
              <div className="flex items-start">
                <div className="flex items-center h-5">
                  <Field
                    type="checkbox"
                    id="dataProcessingConsent"
                    name="dataProcessingConsent"
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                </div>
                <div className="ml-3 text-sm">
                  <label htmlFor="dataProcessingConsent" className="font-medium text-gray-700">
                    I consent to the processing of my data in accordance with the <a href="/privacy" className="text-primary-600 hover:text-primary-500">Privacy Policy</a>
                  </label>
                  <ErrorMessage name="dataProcessingConsent" component="div" className="mt-1 text-sm text-red-600" />
                </div>
              </div>
            </div>
          </div>
        );
        
      case 4: // Complete
        return (
          <div className="text-center py-8">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
              <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="mt-6 text-xl font-medium text-gray-900">Setup Complete!</h3>
            <p className="mt-2 text-sm text-gray-500">
              Your developer account has been created successfully. You can now start using the PropPulse Developer Console.
            </p>
            <div className="mt-6">
              <button
                type="button"
                onClick={() => router.push('/dev/dashboard')}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
              >
                Go to Dashboard
              </button>
            </div>
          </div>
        );
        
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">Welcome to PropPulse</h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          Let's set up your developer account
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          {/* Progress steps */}
          <div className="mb-8">
            <div className="flex items-center justify-between">
              {STEPS.map((step, index) => (
                <div key={step} className="flex flex-col items-center">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      index < currentStep
                        ? 'bg-primary-600 text-white'
                        : index === currentStep
                        ? 'bg-primary-100 text-primary-600 border-2 border-primary-600'
                        : 'bg-gray-100 text-gray-400'
                    }`}
                  >
                    {index < currentStep ? (
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <span>{index + 1}</span>
                    )}
                  </div>
                  <span className="mt-2 text-xs text-gray-500">{step}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 flex justify-between">
              {STEPS.slice(0, -1).map((_, index) => (
                <div
                  key={index}
                  className={`h-1 w-full ${
                    index < currentStep ? 'bg-primary-600' : 'bg-gray-200'
                  }`}
                />
              ))}
            </div>
          </div>

          {/* Form */}
          <Formik
            initialValues={initialValues}
            validationSchema={currentStep < validationSchemas.length ? validationSchemas[currentStep] : null}
            onSubmit={handleSubmit}
          >
            {(formikProps) => (
              <Form>
                {renderStepContent(currentStep, formikProps)}
                
                {currentStep < STEPS.length - 1 && (
                  <div className="mt-8 flex justify-between">
                    <button
                      type="button"
                      onClick={handleBack}
                      disabled={currentStep === 0}
                      className={`px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 ${
                        currentStep === 0 ? 'opacity-50 cursor-not-allowed' : ''
                      }`}
                    >
                      Back
                    </button>
                    
                    <button
                      type="submit"
                      disabled={formikProps.isSubmitting}
                      className="inline-flex justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                    >
                      {currentStep === STEPS.length - 2 ? 'Submit' : 'Next'}
                      {formikProps.isSubmitting && (
                        <svg className="animate-spin ml-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                      )}
                    </button>
                  </div>
                )}
              </Form>
            )}
          </Formik>
        </div>
      </div>
    </div>
  );
};

export default WelcomeWizard;
