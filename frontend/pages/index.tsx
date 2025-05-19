import { useState } from 'react';
import { serverSideTranslations } from 'next-i18next';
import { useTranslation } from 'next-i18next';
import { GetServerSideProps } from 'next';
import {
  Box,
  Container,
  Typography,
  Grid,
  Paper,
  Button,
  Card,
  CardContent,
  CardHeader,
  Divider,
  useTheme,
} from '@mui/material';
import DashboardLayout from '../components/layouts/DashboardLayout';

export default function Dashboard() {
  const { t } = useTranslation('common');
  const theme = useTheme();
  
  // Mock data for dashboard
  const [properties, setProperties] = useState([
    { id: 'PROP_001', name: 'Downtown Apartment', developer: 'Emaar', price: 1250000, yield: 6.8 },
    { id: 'PROP_002', name: 'Marina Penthouse', developer: 'Damac', price: 3500000, yield: 5.9 },
    { id: 'PROP_003', name: 'Palm Villa', developer: 'Nakheel', price: 7800000, yield: 4.7 },
  ]);
  
  const [proposals, setProposals] = useState([
    { id: 'prop_123abc', date: '2025-05-15', properties: 2, status: 'completed' },
    { id: 'prop_456def', date: '2025-05-10', properties: 1, status: 'completed' },
  ]);

  return (
    <DashboardLayout>
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          {t('dashboard.welcome')}
        </Typography>
        
        <Grid container spacing={3}>
          {/* Summary Cards */}
          <Grid item xs={12} md={4}>
            <Card>
              <CardHeader title={t('dashboard.properties')} />
              <CardContent>
                <Typography variant="h3">{properties.length}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {t('dashboard.availableProperties')}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card>
              <CardHeader title={t('dashboard.proposals')} />
              <CardContent>
                <Typography variant="h3">{proposals.length}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {t('dashboard.generatedProposals')}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card>
              <CardHeader title={t('dashboard.averageYield')} />
              <CardContent>
                <Typography variant="h3">
                  {(properties.reduce((acc, prop) => acc + prop.yield, 0) / properties.length).toFixed(1)}%
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {t('dashboard.acrossAllProperties')}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          
          {/* Recent Properties */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                {t('dashboard.recentProperties')}
              </Typography>
              <Divider sx={{ mb: 2 }} />
              
              <Grid container spacing={2}>
                {properties.map((property) => (
                  <Grid item xs={12} md={4} key={property.id}>
                    <Card>
                      <CardContent>
                        <Typography variant="h6">{property.name}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {property.developer}
                        </Typography>
                        <Typography variant="body1" sx={{ mt: 2 }}>
                          AED {property.price.toLocaleString()}
                        </Typography>
                        <Typography variant="body2" color="primary">
                          {property.yield}% {t('dashboard.yield')}
                        </Typography>
                        <Button 
                          variant="contained" 
                          size="small" 
                          sx={{ mt: 2 }}
                        >
                          {t('dashboard.generateProposal')}
                        </Button>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          </Grid>
          
          {/* Recent Proposals */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                {t('dashboard.recentProposals')}
              </Typography>
              <Divider sx={{ mb: 2 }} />
              
              <Grid container spacing={2}>
                {proposals.map((proposal) => (
                  <Grid item xs={12} md={6} key={proposal.id}>
                    <Card>
                      <CardContent>
                        <Typography variant="h6">
                          {t('dashboard.proposalId')}: {proposal.id}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {t('dashboard.generated')}: {proposal.date}
                        </Typography>
                        <Typography variant="body2" sx={{ mt: 1 }}>
                          {t('dashboard.properties')}: {proposal.properties}
                        </Typography>
                        <Typography variant="body2" color="primary">
                          {t('dashboard.status')}: {proposal.status}
                        </Typography>
                        <Button 
                          variant="outlined" 
                          size="small" 
                          sx={{ mt: 2, mr: 1 }}
                        >
                          {t('dashboard.viewPdf')}
                        </Button>
                        <Button 
                          variant="outlined" 
                          size="small" 
                          sx={{ mt: 2 }}
                        >
                          {t('dashboard.share')}
                        </Button>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </DashboardLayout>
  );
}

export const getServerSideProps: GetServerSideProps = async ({ locale }) => {
  return {
    props: {
      ...(await serverSideTranslations(locale || 'en', ['common'])),
    },
  };
};
