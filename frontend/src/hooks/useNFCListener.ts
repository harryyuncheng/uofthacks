import { useState, useEffect } from 'react';

export interface NFCEvent {
    type: string;
    nfc_id?: string;
    user?: any;
    goals?: any[];
    context?: string[];
    timestamp?: string;
    message?: string;
}

export function useNFCListener() {
    const [lastEvent, setLastEvent] = useState<NFCEvent | null>(null);

    useEffect(() => {
        if (!window.electron) return;

        const unsubscribe = window.electron.on('nfc-event', (data: NFCEvent) => {
            console.log('[HOOK] NFC Event:', data);
            setLastEvent(data);
        });

        return () => {
            unsubscribe();
        };
    }, []);

    return lastEvent;
}
