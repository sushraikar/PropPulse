import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Typography, 
  Button, 
  Card, 
  CardContent, 
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';
import { styled } from '@mui/material/styles';

// Styled components
const WidgetContainer = styled(Box)(({ theme }) => ({
  padding: theme.spacing(2),
  height: '100%',
  overflow: 'auto'
}));

const MetricsCard = styled(Card)(({ theme }) => ({
  marginBottom: theme.spacing(2),
  backgroundColor: theme.palette.mode === 'dark' ? '#1A2027' : '#fff',
}));

const ActionButton = styled(Button)(({ theme }) => ({
  margin: theme.spacing(1, 0),
}));

/**
 * PropPulse Zoho CRM Widget Component
 * 
 * This widget displays property investment metrics and proposal options
 * when embedded in Zoho CRM.
 */
const ZohoWidget = () => {
  // State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [entityData, setEntityData] = useState(null);
  const [proposals, setProposals] = useState([]);
  const [language, setLanguage] = useState('English');
  const [generating, setGenerating] = useState(false);

  // Get Zoho CRM entity data on component mount
  useEffect(() => {
    const getZohoData = async () => {
      try {
        // In a real implementation, this would use ZOHO.CRM.API to get data
        // For now, we'll simulate with mock data
        
        // Simulate API delay
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Mock data based on current module
        const mockEntityData = {
          module: 'Properties',
          data: {
            Property_ID: 'PROP_001',
            Project_Name: 'Downtown Residences',
            Developer: 'Emaar Properties',
            Tower_Phase: 'Tower A',
            Unit_No: '1204',
            Unit_Type: '2 Bedroom',
            Size_ft2: 1200,
            View: 'Burj Khalifa',
            List_Price_AED: 1250000,
            Status: 'Available'
          }
        };
        
        // Mock proposals
        const mockProposals = [
          {
            Proposal_ID: 'prop_abc123',
            Contact_Name: 'John Smith',
            Language: 'English',
            Created_On: '2025-05-15T10:30:00Z',
            PDF_Link: 'https://storage.proppulse.ai/proposals/prop_abc123.pdf'
          },
          {
            Proposal_ID: 'prop_def456',
            Contact_Name: 'Ahmed Hassan',
            Language: 'Arabic',
            Created_On: '2025-05-14T14:45:00Z',
            PDF_Link: 'https://storage.proppulse.ai/proposals/prop_def456_ar.pdf'
          }
        ];
        
        setEntityData(mockEntityData);
        setProposals(mockProposals);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching Zoho data:', err);
        setError('Failed to load data from Zoho CRM');
        setLoading(false);
      }
    };
    
    getZohoData();
  }, []);

  // Handle proposal generation
  const handleGenerateProposal = async () => {
    setGenerating(true);
    
    try {
      // In a real implementation, this would call the PropPulse API
      // For now, we'll simulate with a delay
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Add new proposal to list
      const newProposal = {
        Proposal_ID: `prop_${Math.random().toString(36).substr(2, 6)}`,
        Contact_Name: 'Current Contact',
        Language: language,
        Created_On: new Date().toISOString(),
        PDF_Link: `https://storage.proppulse.ai/proposals/new_proposal_${language.toLowerCase()}.pdf`
      };
      
      setProposals([newProposal, ...proposals]);
      setGenerating(false);
    } catch (err) {
      console.error('Error generating proposal:', err);
      setError('Failed to generate proposal');
      setGenerating(false);
    }
  };

  // Handle language change
  const handleLanguageChange = (event) => {
    setLanguage(event.target.value);
  };

  // Loading state
  if (loading) {
    return (
      <WidgetContainer display="flex" justifyContent="center" alignItems="center">
        <CircularProgress />
      </WidgetContainer>
    );
  }

  // Error state
  if (error) {
    return (
      <WidgetContainer>
        <Typography color="error">{error}</Typography>
      </WidgetContainer>
    );
  }

  // Property view
  if (entityData?.module === 'Properties') {
    const property = entityData.data;
    
    return (
      <WidgetContainer>
        <Typography variant="h6" gutterBottom>
          PropPulse Investment Analysis
        </Typography>
        
        {/* Property Summary */}
        <MetricsCard>
          <CardContent>
            <Typography variant="subtitle1" fontWeight="bold">
              {property.Project_Name} - {property.Unit_No}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {property.Unit_Type} | {property.Size_ft2.toLocaleString()} ft² | {property.View}
            </Typography>
            <Typography variant="h6" color="primary">
              AED {property.List_Price_AED.toLocaleString()}
            </Typography>
          </CardContent>
        </MetricsCard>
        
        {/* Investment Metrics */}
        <MetricsCard>
          <CardContent>
            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
              Investment Metrics
            </Typography>
            
            <Box display="flex" justifyContent="space-between" mb={1}>
              <Typography variant="body2">Average Daily Rate (ADR):</Typography>
              <Typography variant="body2" fontWeight="bold">AED 850</Typography>
            </Box>
            
            <Box display="flex" justifyContent="space-between" mb={1}>
              <Typography variant="body2">Occupancy Rate:</Typography>
              <Typography variant="body2" fontWeight="bold">85%</Typography>
            </Box>
            
            <Box display="flex" justifyContent="space-between" mb={1}>
              <Typography variant="body2">Net Yield:</Typography>
              <Typography variant="body2" fontWeight="bold" color="primary">6.8%</Typography>
            </Box>
            
            <Box display="flex" justifyContent="space-between" mb={1}>
              <Typography variant="body2">10-Year IRR:</Typography>
              <Typography variant="body2" fontWeight="bold" color="primary">12.5%</Typography>
            </Box>
            
            <Box display="flex" justifyContent="space-between">
              <Typography variant="body2">Capital Appreciation (CAGR):</Typography>
              <Typography variant="body2" fontWeight="bold">7.0%</Typography>
            </Box>
          </CardContent>
        </MetricsCard>
        
        {/* Generate Proposal */}
        <Box mb={2}>
          <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
            Generate Investment Proposal
          </Typography>
          
          <Box display="flex" alignItems="center" mb={1}>
            <FormControl size="small" sx={{ minWidth: 120, mr: 2 }}>
              <InputLabel id="language-select-label">Language</InputLabel>
              <Select
                labelId="language-select-label"
                value={language}
                label="Language"
                onChange={handleLanguageChange}
              >
                <MenuItem value="English">English</MenuItem>
                <MenuItem value="Arabic">Arabic</MenuItem>
                <MenuItem value="French">French</MenuItem>
                <MenuItem value="Hindi">Hindi</MenuItem>
              </Select>
            </FormControl>
            
            <ActionButton
              variant="contained"
              color="primary"
              onClick={handleGenerateProposal}
              disabled={generating}
            >
              {generating ? <CircularProgress size={24} /> : 'Generate Proposal'}
            </ActionButton>
          </Box>
        </Box>
        
        {/* Recent Proposals */}
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          Recent Proposals
        </Typography>
        
        {proposals.length > 0 ? (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Contact</TableCell>
                  <TableCell>Language</TableCell>
                  <TableCell>Date</TableCell>
                  <TableCell>Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {proposals.map((proposal) => (
                  <TableRow key={proposal.Proposal_ID}>
                    <TableCell>{proposal.Proposal_ID}</TableCell>
                    <TableCell>{proposal.Contact_Name}</TableCell>
                    <TableCell>{proposal.Language}</TableCell>
                    <TableCell>{new Date(proposal.Created_On).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        variant="outlined"
                        href={proposal.PDF_Link}
                        target="_blank"
                      >
                        View PDF
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No proposals generated yet
          </Typography>
        )}
      </WidgetContainer>
    );
  }
  
  // Contact view
  if (entityData?.module === 'Contacts') {
    return (
      <WidgetContainer>
        <Typography variant="h6" gutterBottom>
          PropPulse Investment Proposals
        </Typography>
        
        {/* Recent Proposals */}
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          Client Proposals
        </Typography>
        
        {proposals.length > 0 ? (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Property</TableCell>
                  <TableCell>Language</TableCell>
                  <TableCell>Date</TableCell>
                  <TableCell>Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {proposals.map((proposal) => (
                  <TableRow key={proposal.Proposal_ID}>
                    <TableCell>{proposal.Proposal_ID}</TableCell>
                    <TableCell>Downtown Residences</TableCell>
                    <TableCell>{proposal.Language}</TableCell>
                    <TableCell>{new Date(proposal.Created_On).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        variant="outlined"
                        href={proposal.PDF_Link}
                        target="_blank"
                      >
                        View PDF
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No proposals generated for this client
          </Typography>
        )}
        
        <ActionButton
          variant="contained"
          color="primary"
          fullWidth
        >
          Browse Properties
        </ActionButton>
      </WidgetContainer>
    );
  }
  
  // Fallback view
  return (
    <WidgetContainer>
      <Typography>
        PropPulse widget is ready. Please open a Property or Contact record to view investment data.
      </Typography>
    </WidgetContainer>
  );
};

export default ZohoWidget;
