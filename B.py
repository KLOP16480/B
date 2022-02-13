/*

 * SmsToLead.cls

 *

 * Shows how to receive SMS messages in Apex Code, creating Leads in a Campaign

 */

@RestResource(urlMapping='/smstolead')

global class SmsToLead {

    static TwilioAccount account = TwilioAPI.getDefaultAccount();

    

    @future(callout=true)

    public static void reply(String fromNumber, String toNumber, String message) {

        Map<String, String> params = new Map<String, String>{

          'From' => fromNumber, 

          'To' => toNumber, 

          'Body' => message

        };

        

        TwilioSms sms = account.getSmsMessages().create(params);

        System.debug('Sent SMS SID: '+sms.getSid());

    }

    

    @HttpPost

    global static void incomingSMS() {

        // This will error out with System.LimitException if we would exceed 

        // our daily email limit

        Messaging.reserveSingleEmailCapacity(1);

        String expectedSignature = 

            RestContext.request.headers.get('X-Twilio-Signature');

        String url = 'https://' + RestContext.request.headers.get('Host') + 

            '/services/apexrest' + RestContext.request.requestURI;

        Map <String, String> params = RestContext.request.params;

        // Validate signature

        if (!TwilioAPI.getDefaultClient().validateRequest(expectedSignature, url, params)) {

            RestContext.response.statusCode = 403;

            RestContext.response.responseBody = Blob.valueOf('Failure! Rcvd '+expectedSignature+'\nURL '+url/*+'\nHeaders'+RestContext.request.headers*/);

            return;

        }

        

        // Twilio likes to see something in the response body, otherwise it reports

        // a 502 error in https://www.twilio.com/user/account/log/notifications

        RestContext.response.responseBody = Blob.valueOf('ok');

        

        // Extract useful fields from the incoming SMS

        String leadNumber     = params.get('From');

        String campaignNumber = params.get('To');

        String leadEmail      = params.get('Body');

        

        // Try to find a matching Campaign

        Campaign campaign = null;

        try {

            campaign = [SELECT Id, Name, NumberSent FROM Campaign WHERE Phone__c = :campaignNumber LIMIT 1];

        } catch (QueryException qe) {

            reply(campaignNumber, leadNumber, 'No Campaign configured. Sorry.');

            return;

        }

        

        // Create and insert a new Lead

        Lead lead = new Lead(LastName = 'From SMS',

            Company = 'From SMS',

            Email = leadEmail, 

            Phone = leadNumber);

        try {

            insert lead;

        } catch (DmlException dmle) {

            String message = (dmle.getDmlType(0) == StatusCode.INVALID_EMAIL_ADDRESS)

                ? leadEmail+' doesn\'t look like an email address. Please try again.'

                : 'An error occurred. Sorry.';

            reply(campaignNumber, leadNumber, message);

            return;

        }

        // Link the Lead to the Campaign

        insert new CampaignMember(CampaignId = campaign.Id, LeadId = lead.Id);

        

        // We're done - send an SMS 

        reply(campaignNumber, leadNumber, 'Thanks for registering. We\'ll send you a confirmation email!');

        // Send an email, recording it as an activity

        Messaging.SingleEmailMessage mail = new Messaging.SingleEmailMessage();

        mail.setTargetObjectId(lead.Id);

        mail.setSaveAsActivity(true);

        mail.setSenderDisplayName(campaign.Name);

        mail.setSubject('Welcome!');

        mail.setPlainTextBody('Thanks for registering!');

        Messaging.sendEmail(new Messaging.SingleEmailMessage[] { mail });

    }

}
