import express from 'express';
import { supabaseAdmin } from '../config/supabase.js';
import ragClient from '../config/rag.js';
import { authenticate, optionalAuth } from '../middleware/auth.js';

const router = express.Router();

/**
 * POST /api/schemes/chat
 * Follow-up chat grounded in retrieved schemes
 */
router.post('/chat', optionalAuth, async (req, res) => {
  try {
    const { message, profile } = req.body;
    if (!message || !String(message).trim()) {
      return res.status(400).json({ error: 'Missing message', message: 'Message is required' });
    }

    const p = profile || {};
    const userProfile = {
      age: p.age ? parseInt(p.age) : null,
      gender: p.gender || null,
      income: p.income ? parseFloat(p.income) * 100000 : null,
      state: p.state || null,
      occupation: p.occupation || null,
      caste: p.category || p.caste || null,
      residency: p.residence || p.residency || null,
    };

    const ragResponse = await ragClient.post('/chat', {
      message: String(message).trim(),
      profile: userProfile,
    });

    const ragData = ragResponse.data || {};
    const schemes = (ragData.schemes || []).map((scheme, index) => ({
      id: scheme.scheme_id || `scheme_${index + 1}`,
      name: scheme.scheme_name || 'Government Scheme',
      category: scheme.level || (scheme.categories && scheme.categories[0]) || 'General',
      state: scheme.state || 'All India',
      description: scheme.evidence || '',
      relevanceScore: scheme.score || 0,
      officialWebsite: (scheme.citations && scheme.citations[0]?.source_url) || '',
      matchedSections: scheme.matched_sections || [],
      citations: scheme.citations || [],
      eligibilityStatus: scheme.eligibility_status || null,
      eligibilityReasons: scheme.eligibility_reasons || [],
      eligibilityUnknowns: scheme.eligibility_unknowns || [],
    }));

    res.json({
      answer: ragData.answer || '',
      totalSchemes: schemes.length,
      schemes,
      query: ragData.query || '',
      meta: ragData.meta || {},
      message: ragData.message || String(message).trim(),
      extractedProfile: ragData.extracted_profile || null,
      missingFields: ragData.missing_fields || [],
      extractionSource: ragData.extraction_source || null,
    });
  } catch (error) {
    console.error('Chat error:', error.message);
    if (error.response) {
      return res.status(error.response.status || 500).json({
        error: 'RAG service error',
        message: error.response.data?.detail || 'Failed to chat',
      });
    }
    res.status(500).json({ error: 'Internal server error', message: 'Failed to chat' });
  }
});

/**
 * POST /api/schemes/discover
 * Discover schemes based on user profile using RAG service
 */
router.post('/discover', optionalAuth, async (req, res) => {
  try {
    const {
      gender,
      age,
      state,
      residence,
      category,
      income,
      occupation
    } = req.body;

    console.log('\n--- DISCOVER REQUEST ---');
    console.log('Profile received:', { age, gender, state, residence, category, income, occupation });

    // Validate required fields
    if (!age || !state || !residence || !category || !income || !occupation) {
      return res.status(400).json({ 
        error: 'Missing required fields',
        message: 'All profile fields are required for scheme discovery' 
      });
    }

    // Map frontend data to RAG UserProfile format
    const userProfile = {
      age: parseInt(age),
      gender: gender || 'male',
      income: parseFloat(income) * 100000, // Convert lakhs to rupees
      state: state,
      occupation: occupation,
      caste: category, // RAG uses 'caste' field
      residency: residence // RAG uses 'residency' field
    };

    console.log('Sending to RAG:', userProfile);
    console.log('RAG URL:', process.env.RAG_SERVICE_URL || 'http://localhost:8000');

    // Call RAG service to find matching schemes
    const ragResponse = await ragClient.post('/find-schemes', userProfile);

    console.log('RAG response status:', ragResponse.status);
    console.log('RAG response keys:', Object.keys(ragResponse.data || {}));
    console.log('Schemes returned:', ragResponse.data?.schemes?.length || 0);
    console.log('Has answer:', !!ragResponse.data?.answer);
    console.log('--- END DISCOVER ---\n');

    if (!ragResponse.data) {
      return res.status(500).json({ 
        error: 'RAG service error',
        message: 'Failed to get schemes from RAG service' 
      });
    }

    const ragData = ragResponse.data;

    // Map RAG response to frontend format
    const schemes = (ragData.schemes || []).map((scheme, index) => ({
      id: scheme.scheme_id || `scheme_${index + 1}`,
      name: scheme.scheme_name || 'Government Scheme',
      category: scheme.level || (scheme.categories && scheme.categories[0]) || 'General',
      state: scheme.state || 'All India',
      description: scheme.evidence || '',
      eligibility: null, // Not available as structured field — shown via AI summary
      benefits: null,    // Not available as structured field — shown via AI summary
      documents: null,   // Not available as structured field — shown via AI summary
      relevanceScore: scheme.score || 0,
      officialWebsite: (scheme.citations && scheme.citations[0]?.source_url) || '',
      matchedSections: scheme.matched_sections || [],
      citations: scheme.citations || [],
      eligibilityStatus: scheme.eligibility_status || null,
      eligibilityReasons: scheme.eligibility_reasons || [],
      eligibilityUnknowns: scheme.eligibility_unknowns || [],
    }));

    // If user is authenticated, optionally save the search
    if (req.user) {
      console.log(`User ${req.user.id} discovered ${schemes.length} schemes`);
    }

    res.json({
      answer: ragData.answer || '',
      totalSchemes: schemes.length,
      schemes: schemes,
      query: ragData.query || '',
      meta: ragData.meta || {},
    });
  } catch (error) {
    console.error('\n--- DISCOVER ERROR ---');
    console.error('Error type:', error.code || error.name);
    console.error('Error message:', error.message);
    if (error.response) {
      console.error('RAG responded with status:', error.response.status);
      console.error('RAG response data:', error.response.data);
    } else if (error.code === 'ECONNREFUSED') {
      console.error('RAG service is not running at', process.env.RAG_SERVICE_URL || 'http://localhost:8000');
    } else {
      console.error('Full error:', error);
    }
    console.error('--- END DISCOVER ERROR ---\n');
    
    if (error.response) {
      return res.status(error.response.status || 500).json({ 
        error: 'RAG service error',
        message: error.response.data?.detail || 'Failed to discover schemes' 
      });
    }
    
    res.status(500).json({ 
      error: 'Internal server error',
      message: 'Failed to discover schemes' 
    });
  }
});

/**
 * GET /api/schemes/:schemeId
 * Get detailed information about a specific scheme
 */
router.get('/:schemeId', async (req, res) => {
  try {
    const { schemeId } = req.params;

    const { data: scheme, error } = await supabaseAdmin
      .from('schemes')
      .select('*')
      .eq('id', schemeId)
      .single();

    if (error) {
      if (error.code === 'PGRST116') {
        return res.status(404).json({ 
          error: 'Not found',
          message: 'Scheme not found' 
        });
      }
      
      console.error('Scheme fetch error:', error);
      return res.status(500).json({ 
        error: 'Database error',
        message: 'Failed to fetch scheme' 
      });
    }

    // Transform database format to frontend format
    const schemeData = {
      id: scheme.id,
      name: scheme.name,
      nameHi: scheme.name_hi,
      category: scheme.category,
      categoryHi: scheme.category_hi,
      benefit: scheme.benefit,
      benefitHi: scheme.benefit_hi,
      deadline: scheme.deadline,
      deadlineHi: scheme.deadline_hi,
      description: scheme.description,
      descriptionHi: scheme.description_hi,
      eligibility: scheme.eligibility,
      eligibilityHi: scheme.eligibility_hi,
      benefits: scheme.benefits,
      benefitsHi: scheme.benefits_hi,
      documents: scheme.documents,
      documentsHi: scheme.documents_hi,
      applicationProcess: scheme.application_process,
      applicationProcessHi: scheme.application_process_hi,
      officialWebsite: scheme.official_website,
      ministry: scheme.ministry,
      ministryHi: scheme.ministry_hi
    };

    res.json({ scheme: schemeData });
  } catch (error) {
    console.error('Get scheme error:', error);
    res.status(500).json({ 
      error: 'Internal server error',
      message: 'Failed to get scheme details' 
    });
  }
});

/**
 * GET /api/schemes
 * Get all schemes with optional filtering
 */
router.get('/', async (req, res) => {
  try {
    const { category, ministry, limit = 50, offset = 0 } = req.query;

    let query = supabaseAdmin
      .from('schemes')
      .select('id, name, name_hi, category, category_hi, benefit, benefit_hi, deadline, ministry')
      .range(offset, offset + limit - 1)
      .order('name');

    if (category) {
      query = query.eq('category', category);
    }

    if (ministry) {
      query = query.eq('ministry', ministry);
    }

    const { data: schemes, error, count } = await query;

    if (error) {
      console.error('Schemes fetch error:', error);
      return res.status(500).json({ 
        error: 'Database error',
        message: 'Failed to fetch schemes' 
      });
    }

    res.json({
      schemes: schemes,
      total: count,
      limit: parseInt(limit),
      offset: parseInt(offset)
    });
  } catch (error) {
    console.error('Get schemes error:', error);
    res.status(500).json({ 
      error: 'Internal server error',
      message: 'Failed to get schemes' 
    });
  }
});

/**
 * POST /api/schemes
 * Create a new scheme (admin only)
 */
router.post('/', authenticate, async (req, res) => {
  try {
    // TODO: Add admin role check
    const schemeData = req.body;

    const { data, error } = await supabaseAdmin
      .from('schemes')
      .insert([
        {
          ...schemeData,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      ])
      .select()
      .single();

    if (error) {
      console.error('Create scheme error:', error);
      return res.status(500).json({ 
        error: 'Database error',
        message: 'Failed to create scheme' 
      });
    }

    res.status(201).json({
      message: 'Scheme created successfully',
      scheme: data
    });
  } catch (error) {
    console.error('Create scheme error:', error);
    res.status(500).json({ 
      error: 'Internal server error',
      message: 'Failed to create scheme' 
    });
  }
});

export default router;
