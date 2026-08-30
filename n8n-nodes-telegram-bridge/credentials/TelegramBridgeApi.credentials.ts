import type { ICredentialType, INodeProperties } from 'n8n-workflow';

export class TelegramBridgeApi implements ICredentialType {
	name = 'telegramBridgeApi';

	displayName = 'Telegram Bridge API';

	documentationUrl = 'https://github.com/antapanpathony/n8nptb';

	properties: INodeProperties[] = [
		{
			displayName: 'Bridge Base URL',
			name: 'baseUrl',
			type: 'string',
			default: 'http://127.0.0.1:8811',
			description:
				'Base URL of the locally running telegram_bridge FastAPI service (bind stays 127.0.0.1 on the bridge side).',
		},
	];
}
