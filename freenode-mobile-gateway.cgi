#!/usr/local/bin/perl
use strict;
use warnings;
use LWP::UserAgent;
use JSON;
use YAML;
use CGI;

my $logpath = "/path/to/log/directory";

sub irc_session {
	my ($ua, $nick, $res) = @_;
	my @r = @{from_json($ua->post("http://webchat.freenode.net/e/n", {nick => $nick})->decoded_content)};
	return 0 unless $r[0];
	my ($s, $c) = ($r[1], 10);
	for ($c-- > 0) {
		my $lines = from_json($ua->post("http://webchat.freenode.net/e/s", {s => $s})->decoded_content);
		for (@{$lines}) {
			if (@{$_}[0] eq "c") {
				push @$res, @{$_}[2].' '.@{@{$_}[3]}[1];
				if (@{$_}[1] eq "376" or @{$_}[1] eq "433") {
					$c = 0;
					last;
				}
			}
		}
		sleep 1 if $c > 0;
	}
	return $s;
}

sub irc_join {
	my ($ua, $s, $r) = @_;
	my $res = $ua->post("http://webchat.freenode.net/e/p", {c => "JOIN $r", s => $s});
}

sub irc_say {
	my ($ua, $s, $r, $m) = @_;
	my $res = $ua->post("http://webchat.freenode.net/e/p", {c => "PRIVMSG $r :$m", s => $s});
}

sub irc_recv {
	my ($ua, $s, $res) = @_;
	my $lines = from_json($ua->post("http://webchat.freenode.net/e/s", {s => $s})->decoded_content);
	for (@{$lines}) {
		if (ref($_) ne 'ARRAY') {
			push @$res, 'error!';
			return;
		}
		my @line = @{$_};
		if ($line[0] eq "c") {
			my $a = xss($line[2]);
			my $m = xss(@{$line[3]}[1]);
			if ($a && $m) {
				$a =~ s/!.*$//g;
				push @$res, "&lt;$a&gt; $m";
			} else {
				push @$res, $m;
			}
		}
	}
}

sub irc_bye {
	my ($ua, $id, $r, $m) = @_;
	my $res = $ua->post("http://webchat.freenode.net/e/p", {c => "PART $r $m", s => $id});
}

sub xss {
	my $str = shift || return(undef);
	$str =~ s/&/&amp;/g;
	$str =~ s/</&lt;/g;
	$str =~ s/>/&gt;/g;
	$str =~ s/\"/&quot;/g;
	$str =~ s/\'/&#39;/g; return($str);
}

sub log_load {
	my ($s, $res) = @_;
	my $logfile = "$logpath/webchat-$s.log";
	if (-e $logfile) {
		open my $fh, '<', $logfile;
		while (<$fh>) {
			push @$res, $_;
		}
		close $fh;
	}
}

sub log_save {
	my ($s, $res) = @_;
	my $logfile = "$logpath/webchat-$s.log";
	open my $fh, '>', $logfile;
	print $fh $_ for @$res;
	close $fh;
}

my $q = CGI->new;

my $c = $q->param('c');
my $m = $q->param('m');
my $s = $q->param('s');
my $r = $q->param('r');

my %page = %{Load(join('', <DATA>))};
my $page = $page{'start'};
if ($c) {
	my $ua = LWP::UserAgent->new;
	my @res;
	if ($c eq 'nick') {
		$s = irc_session($ua, $m, \@res);
		if ($s) {
			irc_join($ua, $s, $r) if $s;
			$page = $page{'list'};
		}
	}
	if ($c eq 'update') {
		irc_say($ua, $s, $r, $m) if $m;
		irc_recv($ua, $s, \@res);

		if (length @res) {
			log_save $s, \@res;
		} else {
			log_load $s, \@res;
		}
		$page = $page{'list'};
	}
	my %data = ( s => $s, r => $r, m => join("\n", @res) );
	$page =~ s/\$(\w+)/$data{$1}/ge;
}

print $q->header(-content_type => 'text/html; charset=utf-8');
print $page;
1;
__DATA__
---
start: <html><head><meta http-equiv="Content-Type" content="text/html;charset=utf-8"/><style type="text/css">* {font-family: monospace}</style></head><body><form method="post"><input type="hidden" name="c" value="nick"/>nick:<input type="text" name="m" value=""/><br/>room:<input type="text" name="r" value=""/><br/><input type="submit"/></form></body></html>
list: <html><head><meta http-equiv="Content-Type" content="text/html;charset=utf-8"/><style type="text/css">* {font-family: monospace}</style></head><body><pre>$m</pre><form method="post"><input type="hidden" name="s" value="$s"/><input type="hidden" name="r" value="$r"/><input type="hidden" name="c" value="update"/><input type="text" name="m" value=""/><br/><input type="submit"/></form></body></html>
