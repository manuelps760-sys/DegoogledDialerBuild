import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:sip_ua/sip_ua.dart';

void main() => runApp(const DegoogledDialerApp());

class DegoogledDialerApp extends StatelessWidget {
  const DegoogledDialerApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Degoogled Dialer',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xff3568d4),
            brightness: Brightness.dark,
          ),
          useMaterial3: true,
        ),
        home: const DialerHome(),
      );
}

class DialerHome extends StatefulWidget {
  const DialerHome({super.key});

  @override
  State<DialerHome> createState() => _DialerHomeState();
}

class _DialerHomeState extends State<DialerHome> {
  static const platform = MethodChannel('org.degoogled.dialer/phone');
  final number = TextEditingController();
  final sipUser = TextEditingController();
  final sipPassword = TextEditingController();
  final sipServer = TextEditingController();
  final sipWebSocket = TextEditingController();
  final sipTarget = TextEditingController();
  final SIPUAHelper sipHelper = SIPUAHelper();
  Call? activeSipCall;
  bool sipConnecting = false;
  bool sipRegistered = false;
  bool sipIncoming = false;
  late final _SipCallbacks sipCallbacks = _SipCallbacks(
    onCall: _onSipCallState,
    onRegistration: _onSipRegistration,
    onTransport: _onSipTransport,
  );
  int tab = 0;
  String status = 'Ready. Test a call before relying on this app.';
  String sipStatus = 'Enter your SIP provider details to register.';
  bool defaultDialer = false;
  bool loadingAccounts = false;
  List<Map<String, dynamic>> accounts = [];
  List<Map<String, dynamic>> contacts = [];
  List<Map<String, dynamic>> callHistory = [];
  String? selectedAccountId;
  bool loadingContacts = false;
  bool loadingHistory = false;

  @override
  void initState() {
    super.initState();
    _refreshRole();
    _loadPhoneAccounts();
    sipHelper.addSipUaHelperListener(sipCallbacks);
  }

  Future<void> _refreshRole() async {
    try {
      final held = await platform.invokeMethod<bool>('isDefaultDialer') ?? false;
      if (mounted) setState(() => defaultDialer = held);
    } on PlatformException catch (e) {
      if (mounted) setState(() => status = 'Phone integration: ${e.message ?? e.code}');
    }
  }

  Future<void> _loadPhoneAccounts() async {
    if (mounted) setState(() => loadingAccounts = true);
    try {
      final raw = await platform.invokeMethod<List<dynamic>>('getPhoneAccounts');
      final loaded = (raw ?? []).whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
      if (!mounted) return;
      setState(() {
        accounts = loaded;
        if (selectedAccountId == null || !accounts.any((a) => a['id'] == selectedAccountId)) {
          selectedAccountId = accounts.isEmpty ? null : accounts.first['id'] as String?;
        }
        loadingAccounts = false;
      });
    } on PlatformException catch (e) {
      if (mounted) { setState(() {
        loadingAccounts = false;
        status = 'Could not read SIM accounts: ${e.message ?? e.code}';
      }); }
    }
  }

  Future<void> _loadContacts() async {
    setState(() => loadingContacts = true);
    try {
      final granted = await platform.invokeMethod<bool>('requestContactsPermission') ?? false;
      if (!granted) {
        if (mounted) setState(() { loadingContacts = false; status = 'Allow contacts permission, then tap refresh.'; });
        return;
      }
      final raw = await platform.invokeMethod<List<dynamic>>('getContacts');
      if (mounted) {
        setState(() {
          contacts = (raw ?? []).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
          loadingContacts = false;
        });
      }
    } on PlatformException catch (e) {
      if (mounted) setState(() { loadingContacts = false; status = e.message ?? e.code; });
    }
  }

  Future<void> _loadHistory() async {
    setState(() => loadingHistory = true);
    try {
      final granted = await platform.invokeMethod<bool>('requestCallLogPermission') ?? false;
      if (!granted) {
        if (mounted) setState(() { loadingHistory = false; status = 'Allow call history permission, then tap refresh.'; });
        return;
      }
      final raw = await platform.invokeMethod<List<dynamic>>('getCallHistory');
      if (mounted) {
        setState(() {
          callHistory = (raw ?? []).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
          loadingHistory = false;
        });
      }
    } on PlatformException catch (e) {
      if (mounted) setState(() { loadingHistory = false; status = e.message ?? e.code; });
    }
  }

  void _dialThis(String value) {
    number.text = value;
    number.selection = TextSelection.collapsed(offset: number.text.length);
    setState(() => tab = 0);
  }

  Widget _contactsPage() => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Row(children: [
        Expanded(child: Text('Contacts', style: Theme.of(context).textTheme.titleLarge)),
        IconButton(onPressed: loadingContacts ? null : _loadContacts, icon: const Icon(Icons.refresh), tooltip: 'Load contacts'),
      ]),
      if (loadingContacts) const LinearProgressIndicator(),
      if (contacts.isEmpty && !loadingContacts)
        const Padding(padding: EdgeInsets.all(20), child: Text('Tap refresh to grant permission and load contacts.')),
      ...contacts.map((contact) => ListTile(
        leading: const CircleAvatar(child: Icon(Icons.person)),
        title: Text(contact['name']?.toString().isNotEmpty == true ? contact['name'].toString() : 'Unknown contact'),
        subtitle: Text(contact['number']?.toString() ?? ''),
        onTap: () => _dialThis(contact['number']?.toString() ?? ''),
        trailing: IconButton(icon: const Icon(Icons.call), onPressed: () => _dialThis(contact['number']?.toString() ?? '')),
      )),
    ],
  );

  Widget _historyPage() => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Row(children: [
        Expanded(child: Text('Recent calls', style: Theme.of(context).textTheme.titleLarge)),
        IconButton(onPressed: loadingHistory ? null : _loadHistory, icon: const Icon(Icons.refresh), tooltip: 'Load call history'),
      ]),
      if (loadingHistory) const LinearProgressIndicator(),
      if (callHistory.isEmpty && !loadingHistory)
        const Padding(padding: EdgeInsets.all(20), child: Text('Tap refresh to grant permission and load recent calls.')),
      ...callHistory.map((entry) {
        final type = int.tryParse(entry['type']?.toString() ?? '') ?? 0;
        final icon = type == 1 ? Icons.call_received : type == 2 ? Icons.call_made : Icons.call_missed;
        final date = DateTime.fromMillisecondsSinceEpoch(int.tryParse(entry['date']?.toString() ?? '') ?? 0);
        final name = entry['name']?.toString() ?? '';
        return ListTile(
          leading: Icon(icon),
          title: Text(name.isNotEmpty ? name : (entry['number']?.toString() ?? 'Unknown')),
          subtitle: Text('${entry['number'] ?? ''} • ${date.toLocal()}'),
          onTap: () => _dialThis(entry['number']?.toString() ?? ''),
          trailing: IconButton(icon: const Icon(Icons.call), onPressed: () => _dialThis(entry['number']?.toString() ?? '')),
        );
      }),
    ],
  );

  Future<void> _chooseDefault() async {
    try {
      final granted = await platform.invokeMethod<bool>('requestDefaultDialer') ?? false;
      await _refreshRole();
      if (mounted) {
        setState(() => status = granted
            ? 'Default phone role is active.'
            : 'Default phone role was not granted. Android may have declined the request.');
      }
    } on PlatformException catch (e) {
      if (mounted) setState(() => status = 'Could not request dialer role: ${e.message ?? e.code}');
    }
  }

  Future<void> _call() async {
    final value = number.text.trim();
    if (value.isEmpty) {
      setState(() => status = 'Enter a phone number first.');
      return;
    }
    try {
      final usedTelecom = await platform.invokeMethod<bool>('placeCall', {
        'number': value,
        if (selectedAccountId != null) 'accountId': selectedAccountId,
      });
      if (mounted) { setState(() => status = usedTelecom == true
          ? 'Call request sent using ${_selectedAccountLabel()}. Check the system call screen.'
          : 'Opened Android dialer. Confirm the SIM and tap Call there.'); }
    } on PlatformException catch (e) {
      if (mounted) { setState(() => status = 'Call request failed: ${e.message ?? e.code}'); }
    }
  }

  String _selectedAccountLabel() {
    for (final account in accounts) {
      if (account['id'] == selectedAccountId) return account['label']?.toString() ?? 'selected SIM';
    }
    return 'Android default SIM';
  }

  void _key(String key) {
    number.text += key;
    number.selection = TextSelection.collapsed(offset: number.text.length);
  }

  Widget _simPicker() {
    if (loadingAccounts) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 10),
        child: LinearProgressIndicator(),
      );
    }
    if (accounts.isEmpty) {
      return Row(children: [
        const Expanded(child: Text('SIM selection unavailable; Android will choose the call account.')),
        IconButton(onPressed: _loadPhoneAccounts, tooltip: 'Refresh SIMs', icon: const Icon(Icons.refresh)),
      ]);
    }
    return DropdownButtonFormField<String>(
      value: selectedAccountId,
      decoration: const InputDecoration(labelText: 'Call using SIM', border: OutlineInputBorder()),
      items: accounts.map((account) => DropdownMenuItem<String>(
        value: account['id'] as String,
        child: Text(account['label']?.toString() ?? 'SIM'),
      )).toList(),
      onChanged: (value) => setState(() => selectedAccountId = value),
    );
  }

  Widget _dialPad() {
    const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'];
    return Column(children: [
      TextField(
        controller: number,
        keyboardType: TextInputType.phone,
        textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 28),
        decoration: const InputDecoration(hintText: 'Enter number', border: OutlineInputBorder()),
      ),
      const SizedBox(height: 12),
      _simPicker(),
      const SizedBox(height: 14),
      GridView.count(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        crossAxisCount: 3,
        childAspectRatio: 1.7,
        children: keys.map((k) => Padding(
          padding: const EdgeInsets.all(4),
          child: FilledButton.tonal(onPressed: () => _key(k), child: Text(k, style: const TextStyle(fontSize: 24))),
        )).toList(),
      ),
      const SizedBox(height: 12),
      Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        IconButton(
          onPressed: () {
            if (number.text.isNotEmpty) {
              number.text = number.text.substring(0, number.text.length - 1);
              number.selection = TextSelection.collapsed(offset: number.text.length);
            }
          },
          icon: const Icon(Icons.backspace_outlined),
        ),
        const SizedBox(width: 18),
        FilledButton.icon(onPressed: _call, icon: const Icon(Icons.call), label: const Text('Call')),
        const SizedBox(width: 18),
        IconButton(onPressed: () => setState(() => number.clear()), icon: const Icon(Icons.clear)),
      ]),
      const SizedBox(height: 8),
      Text(status, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
    ]);
  }

  void _onSipRegistration(RegistrationState state) {
    if (!mounted) return;
    setState(() {
      sipRegistered = state.state == RegistrationStateEnum.REGISTERED;
      sipStatus = 'SIP registration: ${state.state?.name ?? 'unknown'}${state.cause == null ? '' : ' — ${state.cause}'}';
    });
  }

  void _onSipTransport(TransportState state) {
    if (!mounted) return;
    setState(() {
      if (state.state == TransportStateEnum.DISCONNECTED) {
        sipRegistered = false;
      }
      if (!sipRegistered) {
        sipStatus = 'SIP transport: ${state.state.name}${state.cause == null ? '' : ' — ${state.cause}'}';
      }
    });
  }

  void _onSipCallState(Call call, CallState state) {
    if (!mounted) return;
    setState(() {
      if (state.state == CallStateEnum.ENDED || state.state == CallStateEnum.FAILED) {
        activeSipCall = null;
        sipIncoming = false;
        sipStatus = state.state == CallStateEnum.FAILED
            ? 'SIP call failed: ${state.cause ?? 'check server, credentials, and audio settings'}'
            : 'SIP call ended.';
      } else {
        activeSipCall = call;
        sipIncoming = call.direction == Direction.incoming &&
            state.state != CallStateEnum.CONFIRMED &&
            state.state != CallStateEnum.ACCEPTED &&
            state.state != CallStateEnum.STREAM;
        sipStatus = 'SIP call: ${state.state.name}';
      }
    });
  }

  Future<void> _connectSip() async {
    final user = sipUser.text.trim();
    final domain = sipServer.text.trim();
    final wsUrl = sipWebSocket.text.trim();
    final password = sipPassword.text;
    if (user.isEmpty || domain.isEmpty || password.isEmpty || wsUrl.isEmpty) {
      setState(() => sipStatus = 'Enter SIP username, password, SIP domain, and WebSocket URL.');
      return;
    }
    final ws = Uri.tryParse(wsUrl);
    if (ws == null || (ws.scheme != 'wss' && ws.scheme != 'ws') || ws.host.isEmpty) {
      setState(() => sipStatus = 'WebSocket URL must be a valid ws:// or wss:// address. Prefer wss:// for encrypted signaling.');
      return;
    }
    if (ws.scheme != 'wss') {
      setState(() => sipStatus = 'Use wss:// for encrypted SIP signaling. Plain ws:// is disabled for safety.');
      return;
    }
    setState(() {
      sipConnecting = true;
      sipStatus = 'Connecting to SIP server…';
    });
    try {
      final settings = UaSettings()
        ..webSocketUrl = wsUrl
        ..uri = 'sip:$user@$domain'
        ..authorizationUser = user
        ..password = password
        ..displayName = user
        ..userAgent = 'DegoogledDialer/1.0'
        ..register = true;
      await sipHelper.start(settings);
      sipHelper.register();
      if (mounted) setState(() {
        sipConnecting = false;
        sipStatus = 'SIP transport started. Waiting for server registration response…';
      });
    } catch (e) {
      if (mounted) setState(() {
        sipConnecting = false;
        sipRegistered = false;
        sipStatus = 'SIP connection failed: $e';
      });
    }
  }

  Future<void> _disconnectSip() async {
    try {
      activeSipCall?.hangup();
      await sipHelper.unregister();
      sipHelper.stop();
    } catch (_) {
      sipHelper.stop();
    }
    if (mounted) setState(() {
      activeSipCall = null;
      sipIncoming = false;
      sipRegistered = false;
      sipConnecting = false;
      sipStatus = 'Disconnected from SIP.';
    });
  }

  Future<void> _makeSipCall() async {
    if (!sipRegistered) {
      setState(() => sipStatus = 'Register with your SIP provider before placing a VoIP call.');
      return;
    }
    final target = sipTarget.text.trim();
    if (target.isEmpty) {
      setState(() => sipStatus = 'Enter the SIP extension or full SIP URI to call.');
      return;
    }
    final uri = target.startsWith('sip:') || target.startsWith('sips:')
        ? target
        : 'sip:$target@${sipServer.text.trim()}';
    try {
      setState(() => sipStatus = 'Calling $uri…');
      final ok = await sipHelper.call(uri, voiceOnly: true);
      if (!ok && mounted) setState(() => sipStatus = 'SIP call could not be started. Check the target and server logs.');
    } catch (e) {
      if (mounted) setState(() => sipStatus = 'SIP call failed to start: $e');
    }
  }

  void _answerSipCall() {
    final call = activeSipCall;
    if (call == null) return;
    try {
      call.answer(sipHelper.buildCallOptions(true));
      setState(() {
        sipIncoming = false;
        sipStatus = 'Answering SIP call…';
      });
    } catch (e) {
      setState(() => sipStatus = 'Could not answer SIP call: $e');
    }
  }

  void _hangupSipCall() {
    try {
      activeSipCall?.hangup();
      setState(() => sipStatus = 'Ending SIP call…');
    } catch (e) {
      setState(() => sipStatus = 'Could not end SIP call: $e');
    }
  }

  Widget _phoneSettings() => ListView(padding: const EdgeInsets.all(18), children: [
    const Icon(Icons.phone_android, size: 48),
    const SizedBox(height: 10),
    Text('Android calling integration', style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 8),
    ListTile(
      leading: Icon(defaultDialer ? Icons.verified : Icons.info_outline),
      title: Text(defaultDialer ? 'Default phone app selected' : 'Default phone app not selected'),
      subtitle: const Text('Android and your carrier control SIM calls, emergency calling, and Telecom permissions.'),
    ),
    FilledButton(onPressed: _chooseDefault, child: const Text('Choose as default phone app')),
    OutlinedButton(onPressed: _refreshRole, child: const Text('Refresh default-phone status')),
    OutlinedButton.icon(onPressed: _loadPhoneAccounts, icon: const Icon(Icons.sim_card), label: const Text('Refresh SIM accounts')),
    const SizedBox(height: 12),
    Text('Detected call accounts: ${accounts.length}'),
    ...accounts.map((a) => ListTile(
      leading: const Icon(Icons.sim_card),
      title: Text(a['label']?.toString() ?? 'SIM'),
      subtitle: Text((a['address']?.toString().isNotEmpty ?? false) ? a['address'].toString() : 'Carrier did not expose a phone number'),
    )),
    const SizedBox(height: 12),
    const Text('If you are using two SIMs, choose the outgoing SIM on the dial pad. Android may still show its own confirmation or account chooser. Test incoming calls and call waiting on-device.'),
  ]);

  Widget _sipPage() => ListView(padding: const EdgeInsets.all(18), children: [
    const Icon(Icons.public, size: 48),
    const SizedBox(height: 10),
    Text('SIP / VoIP', style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 8),
    const Text('Uses SIP over secure WebSocket (WSS) and WebRTC audio. You need an account and a provider/PBX that supports WebSocket SIP and DTLS-SRTP.'),
    const SizedBox(height: 16),
    TextField(controller: sipUser, autocorrect: false, decoration: const InputDecoration(labelText: 'SIP username / auth ID', border: OutlineInputBorder())),
    const SizedBox(height: 12),
    TextField(controller: sipPassword, obscureText: true, autocorrect: false, decoration: const InputDecoration(labelText: 'SIP password', border: OutlineInputBorder())),
    const SizedBox(height: 12),
    TextField(controller: sipServer, autocorrect: false, decoration: const InputDecoration(labelText: 'SIP domain / registrar', hintText: 'pbx.example.com', border: OutlineInputBorder())),
    const SizedBox(height: 12),
    TextField(controller: sipWebSocket, autocorrect: false, keyboardType: TextInputType.url, decoration: const InputDecoration(labelText: 'Secure WebSocket URL', hintText: 'wss://pbx.example.com:8089/ws', border: OutlineInputBorder())),
    const SizedBox(height: 12),
    Row(children: [
      Expanded(child: FilledButton.icon(
        onPressed: sipConnecting || sipRegistered ? null : _connectSip,
        icon: const Icon(Icons.login),
        label: Text(sipConnecting ? 'Connecting…' : 'Register'),
      )),
      const SizedBox(width: 8),
      Expanded(child: OutlinedButton.icon(
        onPressed: sipConnecting || (!sipRegistered && !sipHelper.connected) ? null : _disconnectSip,
        icon: const Icon(Icons.logout),
        label: const Text('Disconnect'),
      )),
    ]),
    const SizedBox(height: 8),
    ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(sipRegistered ? Icons.verified : Icons.info_outline, color: sipRegistered ? Colors.green : null),
      title: Text(sipRegistered ? 'Registered with SIP provider' : 'Not registered'),
      subtitle: Text(sipStatus),
    ),
    const Divider(),
    TextField(controller: sipTarget, autocorrect: false, decoration: const InputDecoration(labelText: 'Extension / SIP URI to call', hintText: '1001 or sip:1001@pbx.example.com', border: OutlineInputBorder())),
    const SizedBox(height: 12),
    FilledButton.icon(onPressed: sipRegistered && activeSipCall == null ? _makeSipCall : null, icon: const Icon(Icons.call), label: const Text('Place VoIP call')),
    if (activeSipCall != null) ...[
      const SizedBox(height: 12),
      Text('Call state: ${activeSipCall!.state.name}'),
      if (sipIncoming) FilledButton.icon(onPressed: _answerSipCall, icon: const Icon(Icons.call), label: const Text('Answer incoming VoIP call')),
      OutlinedButton.icon(onPressed: _hangupSipCall, icon: const Icon(Icons.call_end), label: const Text('Hang up VoIP call')),
    ],
    const SizedBox(height: 12),
    const Text('Credentials stay on this device and are passed to the SIP library for registration. SIP providers differ; successful registration and two-way audio depend on your provider configuration. Do not share your SIP password in chat.'),
  ]);

  @override
  void dispose() {
    number.dispose();
    sipHelper.removeSipUaHelperListener(sipCallbacks);
    sipHelper.stop();
    sipUser.dispose();
    sipPassword.dispose();
    sipServer.dispose();
    sipWebSocket.dispose();
    sipTarget.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Degoogled Dialer'),
      actions: [IconButton(tooltip: 'Default dialer', onPressed: _chooseDefault, icon: const Icon(Icons.phone_android))],
    ),
    body: SafeArea(child: IndexedStack(index: tab, children: [
      SingleChildScrollView(padding: const EdgeInsets.all(18), child: _dialPad()),
      _contactsPage(),
      _historyPage(),
      _phoneSettings(),
      _sipPage(),
    ])),
    bottomNavigationBar: NavigationBar(
      selectedIndex: tab,
      onDestinationSelected: (i) => setState(() => tab = i),
      destinations: const [
        NavigationDestination(icon: Icon(Icons.dialpad), label: 'Dial pad'),
        NavigationDestination(icon: Icon(Icons.contacts), label: 'Contacts'),
        NavigationDestination(icon: Icon(Icons.history), label: 'Recents'),
        NavigationDestination(icon: Icon(Icons.settings_phone), label: 'Phone'),
        NavigationDestination(icon: Icon(Icons.public), label: 'SIP / VoIP'),
      ],
    ),
  );
}

class _SipCallbacks extends SipUaHelperListener {
  _SipCallbacks({
    required this.onCall,
    required this.onRegistration,
    required this.onTransport,
  });

  final void Function(Call call, CallState state) onCall;
  final void Function(RegistrationState state) onRegistration;
  final void Function(TransportState state) onTransport;

  @override
  void callStateChanged(Call call, CallState state) => onCall(call, state);

  @override
  void registrationStateChanged(RegistrationState state) => onRegistration(state);

  @override
  void transportStateChanged(TransportState state) => onTransport(state);

  @override
  void onNewMessage(SIPMessageRequest msg) {}

  @override
  void onNewNotify(Notify ntf) {}

  @override
  void onNewReinvite(ReInvite event) {}
}
