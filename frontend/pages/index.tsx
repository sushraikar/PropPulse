import { useState, useEffect } from 'react';
import axios from 'axios';
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

  const [properties, setProperties] = useState<any[]>([]);
  const [proposals, setProposals] = useState<any[]>([]);
  const [propertiesLoading, setPropertiesLoading] = useState(true);
  const [proposalsLoading, setProposalsLoading] = useState(true);
  const [propertiesError, setPropertiesError] = useState<string | null>(null);
  const [proposalsError, setProposalsError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProperties = async () => {
      setPropertiesLoading(true);
      setPropertiesError(null);
      try {
        const response = await axios.get(`${process.env.NEXT_PUBLIC_API_URL}/properties/`);
        setProperties(response.data);
        setPropertiesLoading(false);
      } catch (error) {
        setPropertiesError('Failed to fetch properties');
        setPropertiesLoading(false);
      }
    };

    const fetchProposals = async () => {
      setProposalsLoading(true);
      setProposalsError(null);
      try {
        const response = await axios.get(`${process.env.NEXT_PUBLIC_API_URL}/proposals/`);
        setProposals(response.data);
        setProposalsLoading(false);
      } catch (error) {
        setProposalsError('Failed to fetch proposals');
        setProposalsLoading(false);
      }
    };

    fetchProperties();
    fetchProposals();
  }, []);

  return (
    <DashboardLayout>
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          {t('dashboard.welcome')}
        </Typography>
        
        <Grid container spacing={3}>
          {/* Summary Cards */}
          {/* Summary Cards */}
          <Grid item xs={12} md={4}>
            <Card>
              <CardHeader title={t('dashboard.properties')} />
              <CardContent>
                {propertiesLoading ? (
                  <Typography>{t('dashboard.loading')}</Typography>
                ) : propertiesError ? (
                  <Typography color="error">{propertiesError}</Typography>
                ) : (
                  <Typography variant="h3">{properties.length}</Typography>
                )}
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
                {proposalsLoading ? (
                  <Typography>{t('dashboard.loading')}</Typography>
                ) : proposalsError ? (
                  <Typography color="error">{proposalsError}</Typography>
                ) : (
                  <Typography variant="h3">{proposals.length}</Typography>
                )}
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
                {propertiesLoading ? (
                  <Typography>{t('dashboard.loading')}</Typography>
                ) : propertiesError ? (
                  <Typography color="error">{propertiesError}</Typography>
                ) : properties.length > 0 ? (
                  <Typography variant="h3">
                    {(properties.reduce((acc, prop) => acc + prop.yield, 0) / properties.length).toFixed(1)}%
                  </Typography>
                ) : (
                  <Typography variant="h3">N/A</Typography>
                )}
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
              {propertiesLoading ? (
                <Typography>{t('dashboard.loadingProperties')}</Typography>
              ) : propertiesError ? (
                <Typography color="error">{propertiesError}</Typography>
              ) : properties.length > 0 ? (
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
              ) : (
                <Typography>{t('dashboard.noPropertiesFound')}</Typography>
              )}
            </Paper>
          </Grid>

          {/* Recent Proposals */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                {t('dashboard.recentProposals')}
              </Typography>
              <Divider sx={{ mb: 2 }} />
              {proposalsLoading ? (
                <Typography>{t('dashboard.loadingProposals')}</Typography>
              ) : proposalsError ? (
                <Typography color="error">{proposalsError}</Typography>
              ) : proposals.length > 0 ? (
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
              ) : (
                <Typography>{t('dashboard.noProposalsFound')}</Typography>
              )}
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
